from pydantic import Field

from typing import Annotated

from ..camera.sensor_control import SensorControl


class SensorControlUpdate(SensorControl):
    __annotations__ = {
        k: Annotated[v, Field(default=None)]
        for k, v in SensorControl.__annotations__.items()
    }
