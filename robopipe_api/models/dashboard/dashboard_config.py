from enum import Enum

from pydantic import ConfigDict

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
    testCases: list[EvalTestCase] = []
    thresholds: list[EvalThreshold] = []
    labels: list[Label] = []
    remoteBackendUrl: str | None = None
