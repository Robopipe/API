import depthai as dai


def from_device_info(device_info: dai.DeviceInfo):
    return {
        "mxid": device_info.mxid,
        "name": device_info.name,
        "platform": device_info.platform.name,
        "protocol": device_info.protocol.name,
        "state": device_info.state.name,
        "status": device_info.status.name,
    }
