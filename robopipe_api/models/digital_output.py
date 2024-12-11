from dataclasses import dataclass
from enum import Enum

from .device import Device


class DigitalOutputMode(Enum):
    Simple = "Simple"
    PWM = "PWM"


@dataclass
class DigitalOutput(Device):
    modes: list[DigitalOutputMode]
    pwm_freq: int
    pwm_duty: int
    value: int | str | bool
    mode: DigitalOutputMode


@dataclass
class DigitalOutputUpdate:
    pwm_freq: int
    pwm_duty: int
    value: int | str | bool
