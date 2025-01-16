from typing import Annotated

from pydantic import BaseModel, Field


class IRConfig(BaseModel):
    flood_light: Annotated[
        float,
        Field(
            ge=0.0,
            le=1.0,
            description="IR LED intensity. Value must be between 0.0 and 1.0",
        ),
    ] = 0.0
    dot_projector: Annotated[
        float,
        Field(
            ge=0.0,
            le=1.0,
            description="Dot projector intensity. Value must be between 0.0 and 1.0",
        ),
    ] = 0.0
