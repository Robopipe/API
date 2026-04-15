import depthai as dai

from math import ceil
from typing import Self

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
        device: dai.Device,
        pipeline: Self | None = None,
        sensors: list[dai.CameraFeatures] = [],
    ):
        self.cameras: dict[str, dai.node.Camera] = {}
        self._streaming_cameras: set[dai.CameraFeatures] = set()
        self._replay_videos: dict[str, str] = {}

        super().__init__(device, pipeline)

        for sensor in sensors:
            self.add_sensor(sensor)

    def recreate(self, pipeline: Self):
        super().recreate(pipeline)
        self._replay_videos = dict(pipeline._replay_videos)

        for sensor in pipeline._streaming_cameras:
            self.add_sensor(sensor)

    def create_camera(self, sensor: dai.CameraFeatures):
        cam = self.pipeline.create(dai.node.Camera)
        self.cameras[sensor.socket.name] = cam
        self._streaming_cameras.add(sensor)
        return cam

    def build_camera(
        self, camera: dai.node.Camera, socket: dai.CameraBoardSocket, **kwargs
    ):
        replay_video_path = self._replay_videos.get(socket.name)
        if replay_video_path is not None:
            replay_video = self.pipeline.create(dai.node.ReplayVideo)
            replay_video.setReplayVideoFile(replay_video_path)
            replay_video.setLoop(True)
            if kwargs.get("replay_size") is not None:
                replay_video.setSize(kwargs["replay_size"])
            camera.build(socket, replay_video)
        else:
            camera.build(
                socket,
                sensorResolution=kwargs.get("resolution"),
                sensorFps=kwargs.get("fps"),
            )

    def add_replay_video(self, socket_name: str, video_path: str):
        self._replay_videos[socket_name] = video_path

    def remove_replay_video(self, socket_name: str):
        if socket_name in self._replay_videos:
            del self._replay_videos[socket_name]

    def add_sensor_config(self, sensor: dai.CameraFeatures):
        self._streaming_cameras.add(sensor)

    def add_sensor(self, sensor: dai.CameraFeatures):
        if not self.__check_sensor(sensor):
            return

        sensor_name = sensor.socket.name
        cam = self.create_camera(sensor)

        still_config = self.__get_sensor_config(sensor, self.MAX_STILL_SIZE)
        video_config = self.__get_sensor_config(sensor, self.MAX_VIDEO_SIZE)

        cam_size, cam_fps = max(
            video_config.resolution, still_config.resolution, key=lambda s: s[0] * s[1]
        ), min(video_config.fps, still_config.fps)
        still_config.fps = video_config.fps = cam_fps
        pool_size = ceil(cam_size[0] * cam_size[1] * self.BYTES_PER_PIXEL * 2)
        cam.setOutputsMaxSizePool(pool_size)
        self.build_camera(cam, sensor.socket, resolution=cam_size, fps=cam_fps)

        self.__build_still_output(cam, sensor_name, still_config)
        self.__build_video_output(cam, sensor_name, video_config)

        control = cam.inputControl.createInputQueue()
        self.add_queue(control, PipelineQueueType.CONTROL, sensor_name, True)

    def remove_sensor(self, sensor_name: str):
        if sensor_name not in map(lambda s: s.socket.name, self._streaming_cameras):
            return

        self.del_queue(sensor_name, PipelineQueueType.STILL)
        self.del_queue(sensor_name, PipelineQueueType.VIDEO)
        self.del_queue(sensor_name, PipelineQueueType.CONTROL)
        del self.cameras[sensor_name]
        self._streaming_cameras = set(
            filter(lambda s: s.socket.name != sensor_name, self._streaming_cameras)
        )

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
        still_out = self.create_mjpeg_encoder(still_out, sensor_name, config.fps)

    def create_mjpeg_encoder(
        self, out: dai.Node.Output, sensor_name: str, fps: int = 30
    ):
        still_enc = self.pipeline.create(dai.node.VideoEncoder)
        still_enc.setDefaultProfilePreset(fps, dai.VideoEncoderProperties.Profile.MJPEG)
        still_enc.setQuality(100)
        out.link(still_enc.input)
        still_enc_out = still_enc.out.createOutputQueue(2, False)
        self.add_queue(still_enc_out, PipelineQueueType.STILL, sensor_name, False)

        return still_enc

    def __build_video_output(
        self, cam: dai.node.Camera, sensor_name: str, config: SensorConfig
    ):
        video_out = cam.requestOutput(
            config.resolution, self.IMG_TYPE, dai.ImgResizeMode.STRETCH, config.fps
        ).createOutputQueue(4, False)
        self.add_queue(video_out, PipelineQueueType.VIDEO, sensor_name, False)
