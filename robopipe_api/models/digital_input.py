from pydantic import BaseModel

from enum import Enum
from typing import Literal

from .device import Device


class DigitalInputMode(Enum):
    Simple = "Simple"
    DirectSwitch = "DirectSwitch"


class DigitalInputCounterMode(Enum):
    Enabled = "Enabled"
    Disabled = "Disabled"


class DigitalInput(Device):
    counter_modes: list[DigitalInputCounterMode]
    modes: list[DigitalInputMode]
    value: Literal[0, 1]
    counter: int
    counter_mode: DigitalInputCounterMode
    mode: DigitalInputMode
    debounce: int = 50


class DigitalInputUpdate(BaseModel):
    counter: int
    counter_mode: DigitalInputCounterMode = DigitalInputCounterMode.Enabled
    mode: DigitalInputMode = DigitalInputMode.Simple
    debounce: int = 50
