from pydantic import BaseModel, Field

from typing import Annotated

from .device import Device


class Modbus(Device):
    value: Annotated[int, Field(ge=0, le=(2**16 - 1))]
    save: bool = True


class ModbusUpdate(BaseModel):
    value: float
