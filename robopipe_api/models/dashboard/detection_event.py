from pydantic import BaseModel


class DetectionEvent(BaseModel):
    id: str
    test_case_id: str
    type: str
    timestamp: str
