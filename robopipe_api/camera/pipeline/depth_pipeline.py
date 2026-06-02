import depthai as dai

from typing import Self

from ..constants import DEPTH_NAME
from .pipeline_queue_type import PipelineQueueType
from .streaming_pipeline import StreamingPipeline


class DepthPipeline(StreamingPipeline):
    def __init__(
        self,
        device: dai.Device,
        pipeline: Self | None = None,
        sensors: list[dai.CameraFeatures] = [],
        stereo_pair: tuple[dai.CameraFeatures, dai.CameraFeatures] | None = None,
    ):
        self.stereo_pair = stereo_pair
        self.stereo: dai.node.StereoDepth | None = None
        self.cam_left: dai.node.Camera | None = None
        self.cam_right: dai.node.Camera | None = None

        super().__init__(device, pipeline, sensors)

        if stereo_pair is not None:
            self.add_stereo_pair(*stereo_pair)

    def recreate(self, pipeline: Self):
        super().recreate(pipeline)
        if pipeline.stereo_pair is not None:
            self.add_stereo_pair(*pipeline.stereo_pair)

    def get_depth_name(self):
        if self.stereo_pair is None:
            return None

        left_name = self.stereo_pair[0].socket.name
        right_name = self.stereo_pair[1].socket.name

        return f"{DEPTH_NAME}_{left_name.split('_')[-1]}_{right_name.split('_')[-1]}"

    def add_sensor(self, sensor):
        if self.stereo_pair is not None and sensor.socket.name in self.stereo_pair:
            self.remove_stereo_pair()

        return super().add_sensor(sensor)

    def add_stereo_pair_config(
        self, left: dai.CameraFeatures, right: dai.CameraFeatures
    ):
        self.stereo_pair = (left, right)

    def add_stereo_pair(self, left: dai.CameraFeatures, right: dai.CameraFeatures):
        left_name = left.socket.name
        right_name = right.socket.name
        if self.stereo_pair == (left, right):
            return
        else:
            self.remove_stereo_pair()
        self.remove_sensor(left_name)
        self.remove_sensor(right_name)

        self.stereo_pair = (left, right)
        depth_name = self.get_depth_name()

        self.cam_left = self.pipeline.create(dai.node.Camera)
        self.cam_right = self.pipeline.create(dai.node.Camera)
        self.stereo = self.pipeline.create(dai.node.StereoDepth)
        self.stereo.setRectification(True)
        self.stereo.setExtendedDisparity(True)
        self.stereo.setSubpixel(False)
        self.stereo.setLeftRightCheck(True)

        self.cam_left.build(left.socket)
        self.cam_right.build(right.socket)
        self.cam_left.requestOutput((640, 400), dai.ImgFrame.Type.GRAY8).link(
            self.stereo.left
        )
        self.cam_right.requestOutput((640, 400), dai.ImgFrame.Type.GRAY8).link(
            self.stereo.right
        )

        video_out = self.stereo.disparity.createOutputQueue(maxSize=2, blocking=False)
        self.add_queue(video_out, PipelineQueueType.VIDEO, depth_name, False)

    def remove_stereo_pair(self):
        if self.stereo_pair is None:
            return

        depth_name = self.get_depth_name()

        self.del_all_queues(depth_name)
        self.stereo_pair = self.stereo = self.cam_left = self.cam_right = None

    def remove_sensor(self, sensor_name: str):
        if sensor_name == self.get_depth_name():
            return self.remove_stereo_pair()

        return super().remove_sensor(sensor_name)
