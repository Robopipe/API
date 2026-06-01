from .base_model import BaseModel


class ReplayInfo(BaseModel):
    replay: bool
    filename: str | None
