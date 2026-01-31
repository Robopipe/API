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
        super().__init__(pipeline, device)

        for sensor in sensors:
            self.add_sensor(sensor)

    def extract_properties(self):
        super().extract_properties()

        for camera in self.cameras.values():
            if not isinstance(camera, dai.node.MonoCamera):
                continue

            for script in self.pipeline.getAllNodes():
                if not isinstance(script, dai.node.Script):
                    continue

                try:
                    camera.out.unlink(script.inputs["in"])
                except:
                    continue

                camera.out.link(script.inputs["in"])
                self.scripts[camera.getBoardSocket().name] = script
                break

    def add_sensor(self, sensor: dai.CameraFeatures):
        sensor_name = sensor.socket.name

        if sensor_name in self.cameras:
            return

        if not (
            dai.CameraSensorType.COLOR
            in sensor.supportedTypes
            # or dai.CameraSensorType.MONO in sensor.supportedTypes
        ):
            return

        print(sensor.configs, sensor.calibrationResolution)
        cam = self.pipeline.create(dai.node.Camera)
        cam.build(sensor.socket, sensorFps=28)
        self.cameras[sensor_name] = cam
        video_out = cam.requestOutput(
            size=(1920, 1080),
            type=dai.ImgFrame.Type.NV12,
            resizeMode=dai.ImgResizeMode.STRETCH,
            fps=28,
        ).createOutputQueue(maxSize=1, blocking=False)
        still_out = cam.requestOutput(
            size=(2000, 1500), type=dai.ImgFrame.Type.NV12, fps=28
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
        # print("kokotinq")
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
