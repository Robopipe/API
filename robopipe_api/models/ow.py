from pydantic import BaseModel

from typing import Literal

from .device import Device


class OWPower(Device):
    value: Literal[0, 1]


class OWPowerUpdate(BaseModel):
    value: Literal[0, 1]


class OWBus(Device):
    bus: str
    interval: int = 10
    do_scan: bool
    do_reset: bool
    scan_interval: int = 60


class OWBusUpdate(BaseModel):
    interval: int = 10
    do_scan: bool = False
    do_reset: bool = False
    scan_interval: int = 60
