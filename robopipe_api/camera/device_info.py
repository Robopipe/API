import depthai as dai

import dataclasses
from enum import Enum


class DevicePlatform(Enum):
    X_LINK_ANY_PLATFORM = dai.XLinkPlatform.X_LINK_ANY_PLATFORM.name
    X_LINK_MYRIAD_X = dai.XLinkPlatform.X_LINK_MYRIAD_X.name
    X_LINK_MYRIAD_2 = dai.XLinkPlatform.X_LINK_MYRIAD_2.name


class DeviceProtocol(Enum):
    X_LINK_ANY_PROTOCOL = dai.XLinkProtocol.X_LINK_ANY_PROTOCOL.name
    X_LINK_IPC = dai.XLinkProtocol.X_LINK_IPC.name
    X_LINK_NMB_OF_PROTOCOLS = dai.XLinkProtocol.name
    X_LINK_PCIE = dai.XLinkProtocol.X_LINK_PCIE.name
    X_LINK_TCP_IP = dai.XLinkProtocol.X_LINK_TCP_IP.name
    X_LINK_USB_CDC = dai.XLinkProtocol.X_LINK_USB_CDC.name
    X_LINK_USB_VSC = dai.XLinkProtocol.X_LINK_USB_VSC.name


class DeviceState(Enum):
    X_LINK_ANY_STATE = dai.XLinkDeviceState.X_LINK_ANY_STATE.name
    X_LINK_BOOTED = dai.XLinkDeviceState.X_LINK_BOOTED.name
    X_LINK_BOOTLOADER = dai.XLinkDeviceState.X_LINK_BOOTLOADER.name
    X_LINK_FLASH_BOOTED = dai.XLinkDeviceState.X_LINK_FLASH_BOOTED.name
    X_LINK_UNBOOTED = dai.XLinkDeviceState.X_LINK_UNBOOTED.name


@dataclasses.dataclass
class DeviceInfo:
    mxid: str
    name: str
    platform: DevicePlatform
    protocol: DeviceProtocol
    state: DeviceState
    status: str

    @classmethod
    def from_device_info(cls, device_info: dai.DeviceInfo):
        return cls(
            device_info.mxid,
            device_info.name,
            DevicePlatform[device_info.platform.name],
            DeviceProtocol[device_info.protocol.name],
            device_info.state.name,
            device_info.status.name,
        )
