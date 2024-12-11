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
def get_all_circuits(devices: DevicesDep):
    return [
        device.full()
        for device_type in DEVICE_TYPES
        for device in devices.by_name(device_type)
    ]


@router.get(r"/{device_type:int}")
def get_all_circuits_of_device_type(devices: DevicesDep, device_type: DeviceType):
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
    [AI, AnalogInput, AnalogInputUpdate],
    [AO, AnalogOutput, AnalogOutputUpdate],
    [DI, DigitalInput, DigitalInputUpdate],
    [DO, DigitalOutput, DigitalOutputUpdate],
    [LED, Led, LedUpdate],
]


def register_device_endpoints(endpoints: list[tuple[str, Any, Any]]):
    for endpoint in endpoints:
        get_all, set_all, get, set = create_endpoints(*endpoint)
        router.add_api_route(rf"/{endpoint[0]}", get_all, methods=["GET"])
        router.add_api_route(rf"/{endpoint[0]}", set_all, methods=["POST"])
        router.add_api_route(rf"/{endpoint[0]}/{{circuit}}", get, methods=["GET"])
        router.add_api_route(rf"/{endpoint[0]}/{{circuit}}", set, methods=["POST"])
