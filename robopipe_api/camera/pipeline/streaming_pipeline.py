import depthai as dai

from .pipeline import Pipeline
from .pipeline_queue_type import PipelineQueueType


class StreamingPipeline(Pipeline):
    def __init__(
        self, sensors: list[dai.CameraFeatures], pipeline: dai.Pipeline | None = None
    ):
        self.scripts: dict[str, dai.node.Script] = {}
        super().__init__(pipeline)

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

        cam_control = self.create_x_link(sensor_name, PipelineQueueType.CONTROL, True)
        cam_still = self.create_x_link(
            sensor_name, PipelineQueueType.STILL, False, False, 1
        )
        cam_video = self.create_x_link(
            sensor_name, PipelineQueueType.VIDEO, False, False, 1
        )

        if dai.CameraSensorType.COLOR in sensor.supportedTypes:
            cam_config = self.create_x_link(sensor_name, PipelineQueueType.CONFIG, True)

            cam = self.pipeline.createColorCamera()
            cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)

            cam_config.out.link(cam.inputConfig)
            cam.still.link(cam_still.input)
            cam.video.link(cam_video.input)
        elif dai.CameraSensorType.MONO in sensor.supportedTypes:
            cam = self.pipeline.createMonoCamera()
            cam.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)

            script = self.pipeline.createScript()
            script.setScript(
                """
                    while True:
                        frame = node.io['in'].get()
                        node.io['video'].send(frame)
                        node.io['still'].send(frame)

                        if "preview" in node.io:
                            node.io['preview'].send(frame)
                """
            )

            script.inputs["in"].setBlocking(False)
            script.inputs["in"].setQueueSize(1)
            cam.out.link(script.inputs["in"])
            script.outputs["still"].link(cam_still.input)
            script.outputs["video"].link(cam_video.input)
            self.scripts[sensor_name] = script
        else:
            return

        cam.setBoardSocket(sensor.socket)
        self.cameras[sensor_name] = cam

        cam_control.out.link(cam.inputControl)

    def remove_sensor(self, sensor_name: str):
        if sensor_name not in self.cameras:
            return

        self.del_all_queues(sensor_name)
        self.pipeline.remove(self.cameras[sensor_name])
        del self.cameras[sensor_name]

        if sensor_name in self.scripts:
            self.pipeline.remove(self.scripts[sensor_name])
            del self.scripts[sensor_name]
