from pydantic import BaseModel, Field

from enum import Enum
from typing import Annotated

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
        Field(
            ge=0,
            le=100,
            description="Mutually exclusive with value. Must be a value between 0 and 100",
        ),
    ]
    value: int
