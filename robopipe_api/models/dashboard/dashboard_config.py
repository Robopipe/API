from enum import Enum

from pydantic import ConfigDict, Field

from .eval_threshold import EvalThreshold

from ..base_model import BaseModel
from .eval_models import EvalTestCase
from .label import Label


class DashboardLineDirection(str, Enum):
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"


class DashboardLineFlow(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    projectId: int
    projectName: str
    lineDirection: DashboardLineDirection
    linePosition: float
    lineFlow: DashboardLineFlow = DashboardLineFlow.POSITIVE
    confidenceThreshold: float = 0.5
    debounceFrames: int = 5
    maxMissingFrames: int = 5
    maxMatchDistance: float = 0.2
    testCases: list[EvalTestCase] = []
    thresholds: list[EvalThreshold] = []
    labels: list[Label] = []
    remoteBackendUrl: str | None = None


class DashboardConfigUpdate(BaseModel):
    confidenceThreshold: float | None = Field(None, ge=0.0, le=1.0)
    debounceFrames: int | None = Field(None, ge=1, le=100)
    maxMissingFrames: int | None = Field(None, ge=0, le=100)
    maxMatchDistance: float | None = Field(None, ge=0.0, le=1.0)
