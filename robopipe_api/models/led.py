from pydantic import BaseModel, Field

from typing import Annotated

from .device import Device


class Led(Device):
    value: Annotated[int, Field(ge=0, le=1)]


class LedUpdate(BaseModel):
    value: Annotated[
        int, Field(ge=0, le=1, description="Must be a value between 0 and 1")
    ]
