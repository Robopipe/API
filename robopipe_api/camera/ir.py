from typing import Annotated

from pydantic import BaseModel, Field


class IRConfig(BaseModel):
    flood_light: Annotated[float, Field(strict=True, ge=0.0, le=1.0)] = 0.0
    dot_projector: Annotated[float, Field(strict=True, ge=0.0, le=1.0)] = 0.0
