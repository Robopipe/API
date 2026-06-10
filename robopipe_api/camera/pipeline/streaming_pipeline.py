import depthai as dai

from math import ceil, floor
from typing import Self

from .pipeline import Pipeline
from .pipeline_queue_type import PipelineQueueType
from ...models.still_config import ImgResizeMode, StillConfig, StillConfigOption


_DAI_RESIZE_MODE: dict[ImgResizeMode, dai.ImgResizeMode] = {
    ImgResizeMode.CROP: dai.ImgResizeMode.CROP,
    ImgResizeMode.STRETCH: dai.ImgResizeMode.STRETCH,
    ImgResizeMode.LETTERBOX: dai.ImgResizeMode.LETTERBOX,
}

# Internal DTO used only for the auto-derived video output pick.
class _VideoConfig:
    def __init__(self, resolution: tuple[int, int], fps: int):
        self.resolution = resolution
        self.fps = fps


class StreamingPipeline(Pipeline):
    MAX_STILL_SIZE = 2000 * 2000
    MAX_VIDEO_SIZE = 1920 * 1080
    IMG_TYPE = dai.ImgFrame.Type.NV12
    BYTES_PER_PIXEL = 1.5

    def __init__(
        self,
        device: dai.Device,
        pipeline: Self | None = None,
        sensors: list[dai.CameraFeatures] = [],
    ):
        self.cameras: dict[str, dai.node.Camera] = {}
        self._streaming_cameras: set[dai.CameraFeatures] = set()
        self._replay_videos: dict[str, str] = {}
        self._still_configs: dict[str, StillConfig] = {}

        super().__init__(device, pipeline)

        for sensor in sensors:
            self.add_sensor(sensor)

    def recreate(self, pipeline: Self):
        super().recreate(pipeline)
        self._replay_videos = dict(pipeline._replay_videos)
        self._still_configs = dict(pipeline._still_configs)

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
            if kwargs.get("fps") is not None:
                replay_video.setFps(kwargs["fps"])
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

        # Use user override if present, else auto-derive and cache it
        if sensor_name in self._still_configs:
            still_cfg = self._still_configs[sensor_name]
        else:
            still_cfg = StreamingPipeline.default_still_config(sensor)
            self._still_configs[sensor_name] = still_cfg

        video_config = self.__get_video_config(sensor)

        still_area = still_cfg.width * still_cfg.height
        video_area = video_config.resolution[0] * video_config.resolution[1]
        cam_size = (still_cfg.width, still_cfg.height) if still_area >= video_area else video_config.resolution
        cam_fps = int(min(video_config.fps, still_cfg.fps))

        # Always write back the effective fps so GET /config and the video
        # encoder bit-rate calculation reflect what the camera actually runs at.
        effective_still = still_cfg.model_copy(update={"fps": cam_fps})
        self._still_configs[sensor_name] = effective_still
        still_cfg = effective_still

        pool_size = ceil(cam_size[0] * cam_size[1] * self.BYTES_PER_PIXEL * 2)
        cam.setOutputsMaxSizePool(pool_size)
        self.build_camera(cam, sensor.socket, resolution=cam_size, fps=cam_fps)

        self.__build_still_output(cam, sensor_name, still_cfg)
        self.__build_video_output(cam, sensor_name, video_config.resolution, cam_fps)

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

    @staticmethod
    def available_configs(features: dai.CameraFeatures) -> list[StillConfigOption]:
        """Return still-output configs for this sensor, filtered by primary type and
        mod-32 width constraint, deduped by (width, height) with unioned fps range."""
        primary_type = None
        for t in (dai.CameraSensorType.COLOR, dai.CameraSensorType.MONO):
            if t in features.supportedTypes:
                primary_type = t
                break

        seen: dict[tuple[int, int], tuple[float, float]] = {}
        for config in features.configs:
            if primary_type is not None and config.type != primary_type:
                continue
            w, h = config.width, config.height
            if w % 32 != 0:
                continue
            if (w, h) in seen:
                seen[(w, h)] = (
                    min(seen[(w, h)][0], config.minFps),
                    max(seen[(w, h)][1], config.maxFps),
                )
            else:
                seen[(w, h)] = (config.minFps, config.maxFps)

        return [
            StillConfigOption(
                width=w,
                height=h,
                min_fps=ceil(min_fps),
                max_fps=floor(max_fps),
            )
            for (w, h), (min_fps, max_fps) in sorted(
                seen.items(), key=lambda x: x[0][0] * x[0][1], reverse=True
            )
        ]

    @classmethod
    def default_still_config(cls, features: dai.CameraFeatures) -> StillConfig:
        """Auto-derive the best still config within MAX_STILL_SIZE."""
        options = cls.available_configs(features)
        best: StillConfigOption | None = None
        for opt in options:
            if opt.width * opt.height > cls.MAX_STILL_SIZE:
                continue
            if best is None:
                best = opt
            elif opt.width * opt.height > best.width * best.height:
                best = opt
            elif (
                opt.width * opt.height == best.width * best.height
                and opt.max_fps > best.max_fps
            ):
                best = opt

        if best is None:
            best = options[-1] if options else StillConfigOption(
                width=0, height=0, min_fps=0, max_fps=0
            )

        return StillConfig(
            width=best.width,
            height=best.height,
            fps=best.max_fps,
            resize_mode=ImgResizeMode.CROP,
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

    def __get_video_config(self, sensor: dai.CameraFeatures) -> _VideoConfig:
        best_w, best_h = 0, 0
        best_fps = 0

        for config in sensor.configs:
            w, h = config.width, config.height
            if w * h > self.MAX_VIDEO_SIZE:
                continue
            if w * h > best_w * best_h or (
                w * h == best_w * best_h and config.maxFps > best_fps
            ):
                best_w, best_h = w, h
                best_fps = int(config.maxFps)

        return _VideoConfig((best_w, best_h), best_fps)

    def __build_still_output(
        self, cam: dai.node.Camera, sensor_name: str, config: StillConfig
    ):
        dai_resize_mode = _DAI_RESIZE_MODE[config.resize_mode]
        still_out = cam.requestOutput(
            (config.width, config.height), self.IMG_TYPE, dai_resize_mode, config.fps
        )
        self.create_mjpeg_encoder(still_out, sensor_name, config.fps)

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
        self,
        cam: dai.node.Camera,
        sensor_name: str,
        resolution: tuple[int, int],
        fps: int,
    ):
        video_out = cam.requestOutput(
            resolution, self.IMG_TYPE, dai.ImgResizeMode.STRETCH, fps
        ).createOutputQueue(4, False)
        self.add_queue(video_out, PipelineQueueType.VIDEO, sensor_name, False)
