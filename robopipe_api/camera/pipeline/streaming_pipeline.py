import depthai as dai

from math import ceil

from .pipeline import Pipeline
from .pipeline_queue_type import PipelineQueueType


class SensorConfig:
    def __init__(self, resolution: tuple[int, int], fps: int):
        self.resolution = resolution
        self.fps = fps


class StreamingPipeline(Pipeline):
    MAX_STILL_SIZE = 2000 * 2000
    MAX_VIDEO_SIZE = 1920 * 1080
    IMG_TYPE = dai.ImgFrame.Type.NV12
    BYTES_PER_PIXEL = 1.5
    MAIN_SENSOR = "CAM_A"

    def __init__(
        self,
        sensors: list[dai.CameraFeatures],
        pipeline: dai.Pipeline | None = None,
        device: dai.Device | None = None,
    ):
        self.scripts: dict[str, dai.node.Script] = {}
        super().__init__(pipeline, device)

        for sensor in sensors:
            if sensor.socket.name == self.MAIN_SENSOR:
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
        if not self.__check_sensor(sensor):
            return

        sensor_name = sensor.socket.name
        cam = self.pipeline.create(dai.node.Camera)
        self.cameras[sensor_name] = cam

        still_config = self.__get_sensor_config(sensor, self.MAX_STILL_SIZE)
        video_config = self.__get_sensor_config(sensor, self.MAX_VIDEO_SIZE)

        cam_size, cam_fps = max(
            video_config.resolution, still_config.resolution, key=lambda s: s[0] * s[1]
        ), min(video_config.fps, still_config.fps)
        still_config.fps = video_config.fps = cam_fps
        pool_size = ceil(cam_size[0] * cam_size[1] * self.BYTES_PER_PIXEL * 2)
        cam.setOutputsMaxSizePool(pool_size)
        cam.build(sensor.socket, cam_size, cam_fps)

        self.__build_still_output(cam, sensor_name, still_config)
        self.__build_video_output(cam, sensor_name, video_config)

        control = cam.inputControl.createInputQueue()
        self.add_queue(control, PipelineQueueType.CONTROL, sensor_name, True)

    def remove_sensor(self, sensor_name: str):
        if sensor_name not in self.cameras:
            return

        self.del_all_queues(sensor_name)
        self.pipeline.remove(self.cameras[sensor_name])
        del self.cameras[sensor_name]

        # Clean up script if exists (used by subclasses)
        if hasattr(self, "scripts") and sensor_name in self.scripts:
            self.pipeline.remove(self.scripts[sensor_name])
            del self.scripts[sensor_name]

    def __check_sensor(self, sensor: dai.CameraFeatures) -> bool:
        if sensor.socket.name in self.cameras:
            return False
        if not (
            dai.CameraSensorType.COLOR in sensor.supportedTypes
            or dai.CameraSensorType.MONO in sensor.supportedTypes
        ):
            return False

        return True

    def __get_sensor_config(
        self, sensor: dai.CameraFeatures, max_size: int
    ) -> SensorConfig:
        best_w, best_h = 0, 0
        best_fps = 0

        for config in sensor.configs:
            w, h = config.width, config.height
            if w * h > max_size:
                continue
            if w * h > best_w * best_h or (
                w * h == best_w * best_h and config.maxFps > best_fps
            ):
                best_w, best_h = w, h
                best_fps = config.maxFps

        return SensorConfig((best_w, best_h), best_fps)

    def __build_still_output(
        self, cam: dai.node.Camera, sensor_name: str, config: SensorConfig
    ):
        # VideoEncoder requires that width is a multiple of 32, so scale down if needed
        # https://docs.luxonis.com/software-v3/depthai/depthai-components/nodes/video_encoder/#VideoEncoder-Limitations
        width, height = config.resolution
        if width % 32 != 0:
            width = (width // 32) * 32
        config.resolution = width, height

        still_out = cam.requestOutput(
            config.resolution, self.IMG_TYPE, dai.ImgResizeMode.CROP, config.fps
        )
        still_enc = self.pipeline.create(dai.node.VideoEncoder)
        still_enc.setDefaultProfilePreset(
            config.fps, dai.VideoEncoderProperties.Profile.MJPEG
        )
        still_enc.setQuality(100)
        still_out.link(still_enc.input)
        still_enc_out = still_enc.out.createOutputQueue(1, False)
        self.add_queue(still_enc_out, PipelineQueueType.STILL, sensor_name, False)

    def __build_video_output(
        self, cam: dai.node.Camera, sensor_name: str, config: SensorConfig
    ):
        video_out = cam.requestOutput(
            config.resolution, self.IMG_TYPE, dai.ImgResizeMode.STRETCH, config.fps
        ).createOutputQueue(4, False)
        self.add_queue(video_out, PipelineQueueType.VIDEO, sensor_name, False)
