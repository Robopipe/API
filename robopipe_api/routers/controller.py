from fastapi import APIRouter

from typing import Any, TypeVar

from ..controller.devices import AI, AO, DI, DO, LED, OWPOWER, OWBUS, REGISTER
from ..models.analog_input import AnalogInput, AnalogInputUpdate
from ..models.analog_output import AnalogOutput, AnalogOutputUpdate
from ..models.digital_input import DigitalInput, DigitalInputUpdate
from ..models.digital_output import DigitalOutput, DigitalOutputUpdate
from ..models.led import Led, LedUpdate
from ..models.modbus import Modbus, ModbusUpdate
from ..models.ow import OWPower, OWPowerUpdate, OWBus, OWBusUpdate
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


def create_endpoints(device_type: str, output_type: S, input_type: T):
    async def get_all(devices: DevicesDep) -> list[output_type]:
        return [device.full() for device in devices.by_name(device_type)]

    async def set_all(devices: DevicesDep, body: input_type) -> list[output_type]:
        return [
            await device.set(**body.model_dump())
            for device in devices.by_name(device_type)
        ]

    async def get(device: DeviceDep) -> output_type:
        return device.full()

    async def set(device: DeviceDep, body: input_type) -> output_type:
        return await device.set(**body.model_dump())

    return [get_all, set_all, get, set]


DEVICE_ENDPOINTS = [
    [AI, AnalogInput, AnalogInputUpdate, "analog input", None],
    [AO, AnalogOutput, AnalogOutputUpdate, "analog output", None],
    [DI, DigitalInput, DigitalInputUpdate, "digital input", None],
    [DO, DigitalOutput, DigitalOutputUpdate, "digital output", None],
    [LED, Led, LedUpdate, "led", None],
    [OWPOWER, OWPower, OWPowerUpdate, "one-wire power supply", "supplies"],
    [OWBUS, OWBus, OWBusUpdate, "one-wire bus", "buses"],
    [REGISTER, Modbus, ModbusUpdate, "modbus register", None],
]


def register_device_endpoints(endpoints: list[tuple[str, Any, Any, str, str | None]]):
    for endpoint in endpoints:
        path, out, inp, name, last_plural = endpoint
        get_all, set_all, get, set = create_endpoints(path, out, inp)
        plural_name = (
            name + "s"
            if last_plural is None
            else " ".join([*name.split(" ")[:-1], last_plural])
        )

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
