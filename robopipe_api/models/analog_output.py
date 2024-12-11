from dataclasses import dataclass
from enum import Enum

from .device import Device


class AnalogOutputModeType(Enum):
    Voltage = "Voltage"
    Current = "Current"
    Resistance = "Resistance"


@dataclass
class AnalogOutputMode:
    value: int
    unit: str
    range: tuple[int, int]


@dataclass
class AnalogOutput(Device):
    modes: dict[AnalogOutputModeType, AnalogOutputMode]
    value: float
    mode: AnalogOutputModeType = AnalogOutputModeType.Voltage


@dataclass
class AnalogOutputUpdate:
    value: float
    mode: AnalogOutputModeType
