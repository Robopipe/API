from enum import Enum

from .base_model import BaseModel
from .device import Device


class AnalogOutputModeType(Enum):
    Voltage = "Voltage"
    Current = "Current"
    Resistance = "Resistance"


class AnalogOutputMode(BaseModel):
    value: int
    unit: str
    range: tuple[int, int]


class AnalogOutput(Device):
    modes: dict[AnalogOutputModeType, AnalogOutputMode]
    value: float
    mode: AnalogOutputModeType = AnalogOutputModeType.Voltage


class AnalogOutputUpdate(BaseModel):
    value: float
    mode: AnalogOutputModeType = AnalogOutputModeType.Voltage
