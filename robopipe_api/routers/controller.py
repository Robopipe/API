from fastapi import APIRouter

from dataclasses import asdict
from typing import Any, TypeVar

from ..controller.devices import AI, AO, DI, DO, LED
from ..models.analog_input import AnalogInput, AnalogInputUpdate
from ..models.analog_output import AnalogOutput, AnalogOutputUpdate
from ..models.digital_input import DigitalInput, DigitalInputUpdate
from ..models.digital_output import DigitalOutput, DigitalOutputUpdate
from ..models.led import Led, LedUpdate
from .common import DevicesDep, DeviceType, DEVICE_TYPES, DeviceDep

router = APIRouter(prefix="/controller", tags=["controller"])


@router.get("/")
def list_all_circuits(devices: DevicesDep):
    return [
        device.full()
        for device_type in DEVICE_TYPES
        for device in devices.by_name(device_type)
    ]


@router.get(r"/{device_type:int}")
def list_all_circuits_of_device_type(devices: DevicesDep, device_type: DeviceType):
    return [device.full() for device in devices.by_name(device_type)]


T = TypeVar("T")
S = TypeVar("S")


def create_endpoints(
    device_type: str,
    output_type: S,
    input_type: T,
):
    async def get_all(devices: DevicesDep) -> list[output_type]:
        return [device.full() for device in devices.by_name(device_type)]

    async def set_all(devices: DevicesDep, body: input_type) -> list[output_type]:
        return [
            await device.set(**asdict(body)) for device in devices.by_name(device_type)
        ]

    async def get(device: DeviceDep) -> output_type:
        return device.full()

    async def set(device: DeviceDep, body: input_type) -> output_type:
        return await device.set(**asdict(body))

    return [get_all, set_all, get, set]


DEVICE_ENDPOINTS = [
    [AI, AnalogInput, AnalogInputUpdate, "analog input"],
    [AO, AnalogOutput, AnalogOutputUpdate, "analog output"],
    [DI, DigitalInput, DigitalInputUpdate, "digital input"],
    [DO, DigitalOutput, DigitalOutputUpdate, "digital output"],
    [LED, Led, LedUpdate, "led"],
]


def register_device_endpoints(endpoints: list[tuple[str, Any, Any, str]]):
    for endpoint in endpoints:
        path, out, inp, name = endpoint
        get_all, set_all, get, set = create_endpoints(path, out, inp)
        plural_name = name + "s"

        router.add_api_route(
            rf"/{path}", get_all, name=f"List all {plural_name}", methods=["GET"]
        )
        router.add_api_route(
            rf"/{path}", set_all, name=f"Set all {plural_name}", methods=["POST"]
        )
        router.add_api_route(
            rf"/{path}/{{circuit}}", get, name=f"Get {name}", methods=["GET"]
        )
        router.add_api_route(
            rf"/{path}/{{circuit}}", set, name=f"Set {name}", methods=["POST"]
        )
