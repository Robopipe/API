from enum import Enum

from pydantic import ConfigDict, Field, field_validator

from .eval_threshold import EvalThreshold

from ..base_model import BaseModel
from .eval_models import EvalTestCase
from .label import Label


def _validate_label_confidence_thresholds(
    value: dict[int, float] | None,
) -> dict[int, float] | None:
    if value is None:
        return value
    for label_id, threshold in value.items():
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"threshold for label {label_id} must be between 0.0 and 1.0"
            )
    return value


class DashboardZoneDirection(str, Enum):
    LeftToRight = "LEFT_TO_RIGHT"
    RightToLeft = "RIGHT_TO_LEFT"
    TopToBottom = "TOP_TO_BOTTOM"
    BottomToTop = "BOTTOM_TO_TOP"


class DashboardCountMode(str, Enum):
    ON_ZONE_ENTER = "ON_ZONE_ENTER"
    ON_CONFIRM = "ON_CONFIRM"


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    projectId: int
    projectName: str
    zoneDirection: DashboardZoneDirection
    zoneCenter: float
    zoneThickness: float = Field(default=0.1, ge=0.0, le=1.0)
    countMode: DashboardCountMode = DashboardCountMode.ON_ZONE_ENTER
    optimistic: bool = True
    confidenceThreshold: float = 0.5
    labelConfidenceThresholds: dict[int, float] = Field(default_factory=dict)
    debounceFrames: int = 5
    maxMissingFrames: int = 5
    maxMatchDistance: float = 0.2
    iouFloor: float = Field(default=0.1, ge=0.0, le=1.0)
    iouCostWeight: float = Field(default=9.4877, ge=0.0)
    mahalanobisGate: float = Field(default=9.4877, ge=0.0)
    ghostGateGrowth: float = Field(default=0.5, ge=0.0)
    processNoisePos: float = Field(default=0.01, gt=0.0)
    processNoiseSize: float = Field(default=0.001, gt=0.0)
    processNoiseVel: float = Field(default=0.001, gt=0.0)
    measurementNoisePos: float = Field(default=0.02, gt=0.0)
    measurementNoiseSize: float = Field(default=0.01, gt=0.0)
    initialVarPos: float = Field(default=0.01, gt=0.0)
    initialVarVel: float = Field(default=1.0, gt=0.0)
    testCases: list[EvalTestCase] = []
    thresholds: list[EvalThreshold] = []
    labels: list[Label] = []
    remoteBackendUrl: str | None = None

    _validate_label_thresholds = field_validator("labelConfidenceThresholds")(
        _validate_label_confidence_thresholds
    )


class DashboardConfigUpdate(BaseModel):
    confidenceThreshold: float | None = Field(None, ge=0.0, le=1.0)
    labelConfidenceThresholds: dict[int, float] | None = None
    debounceFrames: int | None = Field(None, ge=1, le=100)
    maxMissingFrames: int | None = Field(None, ge=0, le=100)
    maxMatchDistance: float | None = Field(None, ge=0.0, le=1.0)
    iouFloor: float | None = Field(None, ge=0.0, le=1.0)
    iouCostWeight: float | None = Field(None, ge=0.0)
    mahalanobisGate: float | None = Field(None, ge=0.0)
    ghostGateGrowth: float | None = Field(None, ge=0.0)
    processNoisePos: float | None = Field(None, gt=0.0)
    processNoiseSize: float | None = Field(None, gt=0.0)
    processNoiseVel: float | None = Field(None, gt=0.0)
    measurementNoisePos: float | None = Field(None, gt=0.0)
    measurementNoiseSize: float | None = Field(None, gt=0.0)
    initialVarPos: float | None = Field(None, gt=0.0)
    initialVarVel: float | None = Field(None, gt=0.0)

    _validate_label_thresholds = field_validator("labelConfidenceThresholds")(
        _validate_label_confidence_thresholds
    )
