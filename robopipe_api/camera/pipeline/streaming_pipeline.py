import depthai as dai

from .pipeline import Pipeline
from .pipeline_queue_type import PipelineQueueType


class StreamingPipeline(Pipeline):
    def __init__(
        self,
        sensors: list[dai.CameraFeatures],
        pipeline: dai.Pipeline | None = None,
        device: dai.Device | None = None,
    ):
        self.scripts: dict[str, dai.node.Script] = {}
        super().__init__(pipeline, device)

        for sensor in sensors:
            self.add_sensor(sensor)

    def extract_properties(self):
        super().extract_properties()

        # In v3, Script nodes are only used for depth pipeline duplication
        # Regular cameras use requestOutput() for multiple outputs
        for script in self.pipeline.getAllNodes():
            if not isinstance(script, dai.node.Script):
                continue
            # Scripts are tracked by subclasses (e.g., DepthPipeline) if needed

    def add_sensor(self, sensor: dai.CameraFeatures):
        sensor_name = sensor.socket.name

        if sensor_name in self.cameras:
            return

        if not (
            dai.CameraSensorType.COLOR in sensor.supportedTypes
            or dai.CameraSensorType.MONO in sensor.supportedTypes
        ):
            return

        cam = self.pipeline.create(dai.node.Camera)
        cam.build(sensor.socket, sensorFps=28)
        self.cameras[sensor_name] = cam

        # Determine frame type based on sensor type
        is_mono = dai.CameraSensorType.MONO in sensor.supportedTypes
        frame_type = dai.ImgFrame.Type.GRAY8 if is_mono else dai.ImgFrame.Type.NV12

        target_fps = 28
        max_video_pixels = 1920 * 1080
        max_still_pixels = 2000 * 2000

        valid_configs = [c for c in sensor.configs if c.maxFps >= target_fps]
        if not valid_configs:
            valid_configs = list(sensor.configs)

        # Video: largest config under 1080p cap
        under_video_cap = [c for c in valid_configs if c.width * c.height <= max_video_pixels]
        if under_video_cap:
            video_config = max(under_video_cap, key=lambda c: c.width * c.height)
        else:
            video_config = min(valid_configs, key=lambda c: c.width * c.height)
        video_size = (video_config.width, video_config.height)

        # Still: largest config under 4MP cap
        under_still_cap = [c for c in valid_configs if c.width * c.height <= max_still_pixels]
        if under_still_cap:
            still_config = max(under_still_cap, key=lambda c: c.width * c.height)
        else:
            still_config = min(valid_configs, key=lambda c: c.width * c.height)
        still_size = (still_config.width, still_config.height)

        video_out = cam.requestOutput(
            size=video_size,
            type=frame_type,
            resizeMode=dai.ImgResizeMode.STRETCH,
            fps=target_fps,
        ).createOutputQueue(maxSize=1, blocking=False)
        still_out = cam.requestOutput(
            size=still_size, type=frame_type, fps=target_fps
        ).createOutputQueue()
        self.add_queue(video_out, PipelineQueueType.VIDEO, sensor_name, False)
        self.add_queue(still_out, PipelineQueueType.STILL, sensor_name, False)
        # cam_control = cam.inputControl.createInputQueue()
        # self.add_queue(cam_control, PipelineQueueType.CONTROL, sensor_name, True)
        # cam_control = self.create_x_link(sensor_name, PipelineQueueType.CONTROL, True)
        # cam_still = self.create_x_link(
        #     sensor_name, PipelineQueueType.STILL, False, False, 1
        # )
        # cam_video = self.create_x_link(
        #     sensor_name, PipelineQueueType.VIDEO, False, False, 1
        # )

        # if not (
        #     dai.CameraSensorType.COLOR in sensor.supportedTypes
        #     or dai.CameraSensorType.MONO in sensor.supportedTypes
        # ):
        #     print(sensor.supportedTypes)
        #     raise ValueError(
        #         f"Sensor {sensor_name} does not support COLOR or MONO camera types."
        #     )
        # cam_config = self.pipeline.create(dai.ImageManipConfig)
        # cam_config = self.create_x_link(sensor_name, PipelineQueueType.CONFIG, True)
        # cam = self.pipeline.create(dai.node.Camera)
        # print("aaaaa")
        # cam.build(sensor.socket)
        # print("bbbbb")
        # cam.requestFullResolutionOutput().createOutputQueue()
        # cam.inputControl.createInputQueue()
        # cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        # cam_config.out.link(cam.inputConfig)
        # cam.still.link(cam_still.input)
        # cam.video.link(cam_video.input)
        # elif dai.CameraSensorType.MONO in sensor.supportedTypes:
        #     cam = self.pipeline.create(dai.node.Camera)
        #     cam.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)

        #     script = self.pipeline.createScript()
        #     script.setScript(
        #         """
        #             while True:
        #                 frame = node.io['in'].get()
        #                 node.io['video'].send(frame)
        #                 node.io['still'].send(frame)

        #                 if "preview" in node.io:
        #                     node.io['preview'].send(frame)
        #         """
        #     )

        #     script.inputs["in"].setBlocking(False)
        #     script.inputs["in"].setQueueSize(1)
        #     cam.out.link(script.inputs["in"])
        #     script.outputs["still"].link(cam_still.input)
        #     script.outputs["video"].link(cam_video.input)
        #     self.scripts[sensor_name] = script
        # else:
        #     return

        # self.cameras[sensor_name] = cam

        # cam_control.out.link(cam.inputControl)

    def remove_sensor(self, sensor_name: str):
        if sensor_name not in self.cameras:
            return

        self.del_all_queues(sensor_name)
        self.pipeline.remove(self.cameras[sensor_name])
        del self.cameras[sensor_name]

        # Clean up script if exists (used by subclasses)
        if hasattr(self, 'scripts') and sensor_name in self.scripts:
            self.pipeline.remove(self.scripts[sensor_name])
            del self.scripts[sensor_name]
