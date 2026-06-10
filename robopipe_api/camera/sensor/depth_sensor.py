import cv2
import depthai as dai

from typing import Callable

from ...models.still_config import ImgResizeMode, StillConfig
from .sensor import Sensor
from ..pipeline.pipeline_queue_type import PipelineQueueType
from ...utils.image import img_frame_to_video_frame


class DepthSensor(Sensor):
    # Matches the hardcoded stereo resolution in DepthPipeline.add_stereo_pair.
    _DEPTH_STILL_CONFIG = StillConfig(
        width=640, height=400, fps=28, resize_mode=ImgResizeMode.CROP
    )

    def __init__(
        self,
        sensor_features: dai.CameraFeatures,
        sensor_nodes: tuple[dai.node.Camera, dai.node.Camera],
        input_queues: dict,
        output_queues: dict,
        restart_pipeline: Callable[[], None],
    ):
        super().__init__(
            sensor_features,
            sensor_nodes[0],
            input_queues,
            output_queues,
            restart_pipeline,
        )

        self.left, self.right = sensor_nodes

    @property
    def config(self) -> StillConfig:
        return self._DEPTH_STILL_CONFIG

    @config.setter
    def config(self, value: StillConfig) -> None:
        pass

    def capture_still(self) -> bytes:
        video_queue = self.output_queues[PipelineQueueType.VIDEO]
        img_frame = video_queue.tryGet() or video_queue.get()
        av_frame = img_frame_to_video_frame(img_frame)
        gray = av_frame.to_ndarray(format="gray")
        _, buf = cv2.imencode(".jpg", gray)
        return buf.tobytes()
