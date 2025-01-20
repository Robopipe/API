from enum import Enum

from .base_model import BaseModel
from .device import Device


class AnalogInputModeType(Enum):
    Disabled = "Disabled"
    Voltage = "Voltage"
    Voltage2V5 = "Voltage2V5"
    Current = "Current"
    Resistance3W = "Resistance3W"
    Resistance2W = "Resistance2W"


class AnalogInputMode(BaseModel):
    value: int
    unit: str
    range: tuple[int, int]


class AnalogInput(Device):
    modes: dict[AnalogInputModeType, AnalogInputMode]
    mode: AnalogInputModeType = AnalogInputModeType.Voltage


class AnalogInputUpdate(BaseModel):
    mode: AnalogInputModeType = AnalogInputModeType.Voltage
