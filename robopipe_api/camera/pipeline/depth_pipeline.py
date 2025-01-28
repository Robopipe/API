import depthai as dai

from .pipeline_queue_type import PipelineQueueType
from .streaming_pipeline import StreamingPipeline

DEPTH_SENSOR_NAME = "DEPTH"


class DepthPipeline(StreamingPipeline):
    def __init__(
        self,
        stereo_pair: tuple[str, str] | None,
        sensors: list[dai.CameraFeatures],
        pipeline: dai.Pipeline | None = None,
    ):
        self.stereo_pair = stereo_pair
        self.stereo_node = None
        self.cam_left_node = None
        self.cam_right_node = None

        super().__init__(sensors, pipeline)

        if stereo_pair is not None:
            self.add_stereo_pair(*stereo_pair)

    def get_depth_name(self):
        if self.stereo_pair is None:
            return None

        return f"DEPTH_{self.stereo_pair[0].split('_')[-1]}_{self.stereo_pair[1].split('_')[-1]}"

    def extract_properties(self):
        super().extract_properties()

        stereo_node: list[dai.node.StereoDepth] = list(
            filter(
                lambda x: isinstance(x, dai.node.StereoDepth),
                self.pipeline.getAllNodes(),
            )
        )

        if stereo_node:
            self.stereo_node = stereo_node[0]

            for camera in self.cameras.values():
                if not isinstance(camera, dai.node.MonoCamera):
                    continue

                try:
                    camera.out.unlink(self.stereo_node.left)
                    camera.out.link(self.stereo_node.left)
                    self.cam_left_node = camera
                except:
                    pass

                try:
                    camera.out.unlink(self.stereo_node.right)
                    camera.out.link(self.stereo_node.right)
                    self.cam_right_node = camera
                except:
                    pass

            self.stereo_pair = (
                self.cam_left_node.getBoardSocket().name,
                self.cam_right_node.getBoardSocket().name,
            )
            del self.cameras[self.cam_left_node.getBoardSocket().name]
            del self.cameras[self.cam_right_node.getBoardSocket().name]

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

        control = self.create_x_link(depth_name, PipelineQueueType.CONTROL, True)
        still = self.create_x_link(depth_name, PipelineQueueType.STILL, False, False, 1)
        video = self.create_x_link(depth_name, PipelineQueueType.VIDEO, False, False, 1)

        cam_left = self.pipeline.createMonoCamera()
        self.cam_left_node = cam_left
        cam_left.setBoardSocket(left_socket)
        cam_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)

        cam_right = self.pipeline.createMonoCamera()
        self.cam_right_node = cam_right
        cam_right.setBoardSocket(right_socket)
        cam_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)

        stereo_depth = self.pipeline.createStereoDepth()
        self.stereo_node = stereo_depth

        script = self.pipeline.createScript()
        self.scripts[depth_name] = script
        script.setScript(
            """
                while True:
                    frame = node.io['in'].get()
                    node.io['video'].send(frame)
                    node.io['still'].send(frame)

                    if "preview" in node.io:
                        node.io["preview"].send(frame)
            """
        )

        cam_left.out.link(stereo_depth.left)
        cam_right.out.link(stereo_depth.right)
        control.out.link(cam_left.inputControl)
        control.out.link(cam_right.inputControl)

        script.inputs["in"].setBlocking(False)
        script.inputs["in"].setQueueSize(1)
        stereo_depth.disparity.link(script.inputs["in"])
        stereo_depth.setNumFramesPool(10)

        script.outputs["still"].link(still.input)
        script.outputs["video"].link(video.input)

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
