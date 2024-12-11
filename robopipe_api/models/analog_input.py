from dataclasses import dataclass
from enum import Enum

from .device import Device


class AnalogInputModeType(Enum):
    Disabled = "Disabled"
    Voltage = "Voltage"
    Voltage2V5 = "Voltage2V5"
    Current = "Current"
    Resistance3W = "Resistance3W"
    Resistance2W = "Resistance2W"


@dataclass
class AnalogInputMode:
    value: int
    unit: str
    range: tuple[int, int]


@dataclass
class AnalogInput(Device):
    modes: dict[AnalogInputModeType, AnalogInputMode]
    mode: AnalogInputModeType = AnalogInputModeType.Voltage


@dataclass
class AnalogInputUpdate:
    mode: AnalogInputModeType
