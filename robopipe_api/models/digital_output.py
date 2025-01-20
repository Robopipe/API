from pydantic import Field

from enum import Enum
from typing import Annotated

from .base_model import BaseModel
from .device import Device


class DigitalOutputMode(Enum):
    Simple = "Simple"
    PWM = "PWM"


class DigitalOutput(Device):
    modes: list[DigitalOutputMode]
    pwm_freq: float
    pwm_duty: Annotated[
        int, Field(ge=0, le=100, description="Mutually exclusive with value")
    ]
    value: int
    modes: list[DigitalOutputMode]
    mode: DigitalOutputMode


class DigitalOutputUpdate(BaseModel):
    pwm_freq: float
    pwm_duty: Annotated[
        int,
        Field(ge=0, le=100, description="Mutually exclusive with value"),
    ]
    value: int
