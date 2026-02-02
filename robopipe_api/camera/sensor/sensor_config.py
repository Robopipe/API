import depthai as dai

from dataclasses import dataclass, asdict


@dataclass
class ConfigProperties:
    @classmethod
    def parse_from_node(cls, node: dai.node.Camera): ...

    def update_node(self, node: dai.node.Camera): ...


@dataclass
class CameraConfigProperties(ConfigProperties):
    """Configuration properties for v3 Camera node.

    Note: In depthai v3, camera sizes are configured via requestOutput()
    rather than directly on the node. These properties are for reference.
    """
    fps: float

    @classmethod
    def parse_from_node(cls, node: dai.node.Camera):
        # In v3, fps is set during build()
        return cls(fps=28)

    def update_node(self, node: dai.node.Camera):
        # In v3, configuration is done at build time and via requestOutput()
        # This method is kept for API compatibility but has limited effect
        pass


CONFIG_PROPERTIES: dict[type, type[ConfigProperties]] = {
    dai.node.Camera: CameraConfigProperties,
}


class SensorConfig:
    def __init__(self, camera_node: dai.node.Camera):
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


SensorConfigProperties = CameraConfigProperties
