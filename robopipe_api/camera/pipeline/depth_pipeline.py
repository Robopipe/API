import depthai as dai

from ...log import logger
from .pipeline_queue_type import PipelineQueueType
from .streaming_pipeline import StreamingPipeline

DEPTH_SENSOR_NAME = "DEPTH"


class DepthPipeline(StreamingPipeline):
    def __init__(
        self,
        stereo_pair: tuple[str, str] | None,
        sensors: list[dai.CameraFeatures],
        pipeline: dai.Pipeline | None = None,
        device: dai.Device | None = None,
    ):
        self.stereo_pair = stereo_pair
        self.stereo_node: dai.node.StereoDepth | None = None
        self.cam_left_node: dai.node.Camera | None = None
        self.cam_right_node: dai.node.Camera | None = None

        super().__init__(sensors, pipeline, device)

        if stereo_pair is not None:
            self.add_stereo_pair(*stereo_pair)

    def get_depth_name(self):
        if self.stereo_pair is None:
            return None

        return f"DEPTH_{self.stereo_pair[0].split('_')[-1]}_{self.stereo_pair[1].split('_')[-1]}"

    def extract_properties(self):
        super().extract_properties()

        stereo_nodes = [
            n for n in self.pipeline.getAllNodes()
            if isinstance(n, dai.node.StereoDepth)
        ]

        if stereo_nodes:
            self.stereo_node = stereo_nodes[0]

            # Find cameras linked to stereo node
            for camera in list(self.cameras.values()):
                socket_name = camera.getBoardSocket().name
                # In v3, we track which cameras are used for stereo via socket
                # The actual linking is done in add_stereo_pair

            for script in self.pipeline.getAllNodes():
                if not isinstance(script, dai.node.Script):
                    continue

                try:
                    self.stereo_node.disparity.unlink(script.inputs["in"])
                    self.stereo_node.disparity.link(script.inputs["in"])
                    self.scripts[self.get_depth_name()] = script
                    break
                except:
                    continue

    def add_sensor(self, sensor):
        if self.stereo_pair is not None and sensor.socket.name in self.stereo_pair:
            self.remove_stereo_pair()

        return super().add_sensor(sensor)

    def add_stereo_pair(self, left: str, right: str):
        if self.stereo_pair is not None:
            if self.stereo_pair == (left, right):
                return
            else:
                self.remove_stereo_pair()

        self.stereo_pair = (left, right)
        depth_name = self.get_depth_name()
        left_socket = dai.CameraBoardSocket.__members__[left]
        right_socket = dai.CameraBoardSocket.__members__[right]
        self.remove_sensor(left_socket.name)
        self.remove_sensor(right_socket.name)

        # Create Camera nodes for stereo pair (v3 unified Camera node)
        cam_left = self.pipeline.create(dai.node.Camera)
        cam_left.build(left_socket)
        self.cam_left_node = cam_left

        cam_right = self.pipeline.create(dai.node.Camera)
        cam_right.build(right_socket)
        self.cam_right_node = cam_right

        # Create StereoDepth node
        stereo_depth = self.pipeline.create(dai.node.StereoDepth)
        self.stereo_node = stereo_depth

        # Link camera outputs to stereo depth (640x400 for performance)
        cam_left.requestOutput((640, 400), dai.ImgFrame.Type.GRAY8).link(stereo_depth.left)
        cam_right.requestOutput((640, 400), dai.ImgFrame.Type.GRAY8).link(stereo_depth.right)

        # Create output queues for disparity
        video_out = stereo_depth.disparity.createOutputQueue(maxSize=4, blocking=False)
        still_out = stereo_depth.disparity.createOutputQueue(maxSize=2, blocking=False)

        self.add_queue(video_out, PipelineQueueType.VIDEO, depth_name, False)
        self.add_queue(still_out, PipelineQueueType.STILL, depth_name, False)

        stereo_depth.setNumFramesPool(10)

    def remove_stereo_pair(self):
        if self.stereo_pair is None:
            return

        depth_name = self.get_depth_name()

        self.del_all_queues(depth_name)
        self.pipeline.remove(self.stereo_node)
        self.pipeline.remove(self.cam_left_node)
        self.pipeline.remove(self.cam_right_node)

        self.stereo_pair = None
        self.stereo_node = None
        self.cam_left_node = None
        self.cam_right_node = None

        if depth_name in self.scripts:
            self.pipeline.remove(self.scripts[depth_name])
            del self.scripts[depth_name]

    def remove_sensor(self, sensor_name: str):
        if sensor_name == self.get_depth_name():
            return self.remove_stereo_pair()

        return super().remove_sensor(sensor_name)
