import depthai as dai

from dataclasses import dataclass, asdict
from enum import Enum

CameraNode = dai.node.Camera | dai.node.ColorCamera | dai.node.MonoCamera


@dataclass
class ConfigProperties:
    @classmethod
    def parse_from_node(cls, node: CameraNode): ...

    def update_node(self, node: CameraNode): ...


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


class ColorCameraResolution(Enum):
    THE_1080_P = dai.ColorCameraProperties.SensorResolution.THE_1080_P.name
    THE_1200_P = dai.ColorCameraProperties.SensorResolution.THE_1200_P.name
    THE_12_MP = dai.ColorCameraProperties.SensorResolution.THE_12_MP.name
    THE_1352X1012 = dai.ColorCameraProperties.SensorResolution.THE_1352X1012.name
    THE_13_MP = dai.ColorCameraProperties.SensorResolution.THE_13_MP.name
    THE_1440X1080 = dai.ColorCameraProperties.SensorResolution.THE_1440X1080.name
    THE_2024X1520 = dai.ColorCameraProperties.SensorResolution.THE_2024X1520.name
    THE_4000X3000 = dai.ColorCameraProperties.SensorResolution.THE_4000X3000.name
    THE_48_MP = dai.ColorCameraProperties.SensorResolution.THE_48_MP.name
    THE_4_K = dai.ColorCameraProperties.SensorResolution.THE_4_K.name
    THE_5312X6000 = dai.ColorCameraProperties.SensorResolution.THE_5312X6000.name
    THE_5_MP = dai.ColorCameraProperties.SensorResolution.THE_5_MP.name
    THE_720_P = dai.ColorCameraProperties.SensorResolution.THE_720_P.name
    THE_800_P = dai.ColorCameraProperties.SensorResolution.THE_800_P.name


@dataclass
class ColorCameraConfigProperties(ConfigProperties):
    resolution: ColorCameraResolution
    still_size: tuple[int, int]
    preview_size: tuple[int, int]
    video_size: tuple[int, int]
    sensor_crop: tuple[float, float]
    fps: float

    @classmethod
    def parse_from_node(cls, node: dai.node.ColorCamera):
        return cls(
            ColorCameraResolution(node.getResolution().name),
            node.getStillSize(),
            node.getPreviewSize(),
            node.getVideoSize(),
            node.getSensorCrop(),
            node.getFps(),
        )

    def update_node(self, node: dai.node.ColorCamera):
        node.setResolution(
            dai.ColorCameraProperties.SensorResolution.__members__[
                self.resolution.value
            ]
        )
        node.setStillSize(self.still_size)
        node.setPreviewSize(self.preview_size)
        node.setVideoSize(self.video_size)
        node.setSensorCrop(*self.sensor_crop)
        node.setFps(self.fps)


class MonoCameraResolution(Enum):
    THE_1200_P = dai.MonoCameraProperties.SensorResolution.THE_1200_P.name
    THE_400_P = dai.MonoCameraProperties.SensorResolution.THE_400_P.name
    THE_480_P = dai.MonoCameraProperties.SensorResolution.THE_480_P.name
    THE_720_P = dai.MonoCameraProperties.SensorResolution.THE_720_P.name
    THE_800_P = dai.MonoCameraProperties.SensorResolution.THE_800_P.name


@dataclass
class MonoCameraConfigProperties(ConfigProperties):
    resolution: MonoCameraResolution
    fps: float

    @classmethod
    def parse_from_node(cls, node: dai.node.MonoCamera):
        return cls(MonoCameraResolution(node.getResolution().name), node.getFps())

    def update_node(self, node: dai.node.MonoCamera):
        node.setResolution(
            dai.MonoCameraProperties.SensorResolution.__members__[self.resolution.value]
        )
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
            **(asdict(self.properties) | asdict(value))
        ).update_node(self.camera_node)


SensorConfigProperties = (
    CameraConfigProperties | ColorCameraConfigProperties | MonoCameraConfigProperties
)
