import depthai as dai

from ...log import logger
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
        if sensor_name != 'CAM_A':
            return
        logger.debug(f"[StreamingPipeline.add_sensor] Adding sensor: {sensor_name}")

        if sensor_name in self.cameras:
            logger.debug(f"[StreamingPipeline.add_sensor] Sensor {sensor_name} already exists, skipping")
            return

        if not (
            dai.CameraSensorType.COLOR in sensor.supportedTypes
            or dai.CameraSensorType.MONO in sensor.supportedTypes
        ):
            logger.debug(f"[StreamingPipeline.add_sensor] Sensor {sensor_name} is not COLOR or MONO, skipping")
            return

        self._check_device(f"before creating Camera node for {sensor_name}")
        logger.debug(f"[StreamingPipeline.add_sensor] Creating Camera node for {sensor_name}")
        cam = self.pipeline.create(dai.node.Camera)
        self._check_device(f"after creating Camera node for {sensor_name}")
        logger.debug(f"[StreamingPipeline.add_sensor] Building Camera node with socket={sensor.socket}")
        self._check_device(f"after building Camera node for {sensor_name}")
        logger.debug(f"[StreamingPipeline.add_sensor] Camera node built for {sensor_name}")
        self.cameras[sensor_name] = cam

        # Determine frame type based on sensor type
        is_mono = dai.CameraSensorType.MONO in sensor.supportedTypes
        frame_type = dai.ImgFrame.Type.YUV420p if is_mono else dai.ImgFrame.Type.NV12

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
        cam.setMaxSizePools(1, 1, 1)
        cam.build(sensor.socket, sensorFps=28)
        video_output = cam.requestOutput(
            size=video_size,
            type=frame_type,
            resizeMode=dai.ImgResizeMode.STRETCH,
            fps=target_fps,
        )
        # still_out = cam.requestOutput(
        #     size=still_size, type=frame_type, fps=target_fps
        # ).createOutputQueue(maxSize=2, blocking=False)
        video_enc = self.pipeline.create(dai.node.VideoEncoder)
        video_enc.setDefaultProfilePreset(28, dai.VideoEncoderProperties.Profile.H264_MAIN)
        # video_enc.setLossless(True)
        # video_enc.setQuality(10)
        video_enc.setNumFramesPool(10)
        video_enc.setMaxOutputFrameSize(5 * 1024 * 1024)  # 2 MB
        video_output.link(video_enc.input)
        # video_out = video_enc.bitstream.createOutputQueue(
        #     maxSize=1, blocking=False
        # )
        video_out = video_enc.out.createOutputQueue(maxSize=1, blocking=False)
        self.add_queue(video_out, PipelineQueueType.VIDEO, sensor_name, False)
        # self.add_queue(still_out, PipelineQueueType.STILL, sensor_name, False)

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
