import depthai as dai

import dataclasses


@dataclasses.dataclass
class DeviceInfo:
    mxid: str
    name: str
    platform: str
    protocol: str
    state: str
    status: str

    @classmethod
    def from_device_info(cls, device_info: dai.DeviceInfo):
        return cls(
            device_info.mxid,
            device_info.name,
            device_info.platform.name,
            device_info.protocol.name,
            device_info.state.name,
            device_info.status.name,
        )
