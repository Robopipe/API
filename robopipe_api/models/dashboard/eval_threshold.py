from ..base_model import BaseModel


class EvalThreshold(BaseModel):
    id: str
    name: str
    value: float
    color: str
    testCaseId: str | None = None
