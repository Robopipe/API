from pydantic import BaseModel


class DetectionEvent(BaseModel):
    id: str
    item_id: int
    type: str
    timestamp: str
