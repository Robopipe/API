import depthai as dai

from dataclasses import dataclass, asdict

CameraNode = dai.node.Camera | dai.node.ColorCamera | dai.node.MonoCamera


@dataclass
class ConfigProperties:
    @classmethod
    def parse_from_node(cls, node: CameraNode):
        pass

    def update_node(self, node: CameraNode):
        pass


@dataclass
class CameraConfigProperties(ConfigProperties):
    resolution: tuple[int, int]
    still_size: tuple[int, int]
    preview_size: tuple[int, int]
    video_size: tuple[int, int]
    fps: float

    @classmethod
    def parse_from_node(cls, node: dai.node.Camera):
        return cls(
            node.getSize(),
            node.getStillSize(),
            node.getPreviewSize(),
            node.getVideoSize(),
            node.getFps(),
        )

    def update_node(self, node: dai.node.Camera):
        node.setSize(self.resolution)
        node.setStillSize(self.still_size)
        node.setPreviewSize(self.preview_size)
        node.setVideoSize(self.video_size)
        node.setFps(self.fps)


@dataclass
class ColorCameraConfigProperties(ConfigProperties):
    resolution: int  # dai.ColorCameraProperties.SensorResolution.value
    still_size: tuple[int, int]
    preview_size: tuple[int, int]
    video_size: tuple[int, int]
    fps: float

    @classmethod
    def parse_from_node(cls, node: dai.node.ColorCamera):
        return cls(
            node.getResolution().value,
            node.getStillSize(),
            node.getPreviewSize(),
            node.getVideoSize(),
            node.getFps(),
        )

    def update_node(self, node: dai.node.ColorCamera):
        node.setResolution(dai.ColorCameraProperties.SensorResolution(self.resolution))
        node.setStillSize(self.still_size)
        node.setPreviewSize(self.preview_size)
        node.setVideoSize(self.video_size)
        node.setFps(self.fps)


@dataclass
class MonoCameraConfigProperties(ConfigProperties):
    resolution: int  # dai.MonoCameraProperties.SensorResolution.value
    fps: float

    @classmethod
    def parse_from_node(cls, node: dai.node.MonoCamera):
        return cls(node.getResolution().value, node.getFps())

    def update_node(self, node: dai.node.MonoCamera):
        node.setResolution(dai.MonoCameraProperties.SensorResolution(self.resolution))
        node.setFps(self.fps)


CONFIG_PROPERTIES: dict[CameraNode, ConfigProperties] = {
    dai.node.Camera: CameraConfigProperties,
    dai.node.ColorCamera: ColorCameraConfigProperties,
    dai.node.MonoCamera: MonoCameraConfigProperties,
}


class SensorConfig:
    def __init__(
        self, camera_node: dai.node.Camera | dai.node.ColorCamera | dai.node.MonoCamera
    ):
        self.camera_node = camera_node

    @property
    def properties(self) -> ConfigProperties:
        return CONFIG_PROPERTIES[type(self.camera_node)].parse_from_node(
            self.camera_node
        )

    @properties.setter
    def properties(self, value: dict):
        CONFIG_PROPERTIES[type(self.camera_node)](
            **(asdict(self.properties) | value)
        ).update_node(self.camera_node)


SensorConfigProperties = (
    CameraConfigProperties | ColorCameraConfigProperties | MonoCameraConfigProperties
)
