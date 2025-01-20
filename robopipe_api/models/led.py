from pydantic import Field

from typing import Annotated

from .base_model import BaseModel
from .device import Device


class Led(Device):
    value: Annotated[int, Field(ge=0, le=1)]


class LedUpdate(BaseModel):
    value: Annotated[int, Field(ge=0, le=1)]
