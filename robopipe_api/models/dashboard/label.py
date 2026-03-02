from ..base_model import BaseModel


class Label(BaseModel):
    id: int
    name: str
    color: str
    createdAt: str
    updatedAt: str
    deletedAt: str | None
