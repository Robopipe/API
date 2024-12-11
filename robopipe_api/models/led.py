from dataclasses import dataclass
from enum import Enum

from .device import Device


class DigitalOutputMode(Enum):
    Simple = "Simple"
    PWM = "PWM"


@dataclass
class Led(Device):
    value: str | int | bool


@dataclass
class LedUpdate:
    value: str | int | bool
