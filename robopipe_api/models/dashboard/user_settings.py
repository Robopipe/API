from typing import Literal

from pydantic import Field, field_validator

from ..base_model import BaseModel


DetectionDisplayMode = Literal[
    "all", "detections_only", "alerts", "alerts_and_warnings"
]
MultiLimitDisplayMode = Literal["highest", "show_all"]
WidgetDisplayMode = Literal["failures", "pass_rate", "failures_of_total"]
MasterDisplayMode = Literal["zone", "grade"]
TimerLabelDisplay = Literal["project_name", "dashboard_name", "nothing"]


class WidgetSlot(BaseModel):
    id: str
    mode: WidgetDisplayMode = "failures"


class WidgetConfig(BaseModel):
    gridSize: int = Field(default=3, ge=1, le=8)
    slots: list[WidgetSlot | None] = []
    masterVisible: bool = True
    masterDisplayMode: MasterDisplayMode = "zone"


TUNING_OVERRIDE_FIELDS: tuple[str, ...] = (
    "confidenceThreshold",
    "labelConfidenceThresholds",
    "debounceFrames",
    "maxMissingFrames",
    "maxMatchDistance",
    "iouFloor",
    "iouCostWeight",
    "mahalanobisGate",
    "ghostGateGrowth",
    "processNoisePos",
    "processNoiseSize",
    "processNoiseVel",
    "measurementNoisePos",
    "measurementNoiseSize",
    "initialVarPos",
    "initialVarVel",
)


class DashboardUserSettings(BaseModel):
    displayMode: DetectionDisplayMode = "all"
    multiLimitMode: MultiLimitDisplayMode = "highest"
    hiddenLabelIds: list[int] = []
    zoneVisible: bool = False
    selectedLabelId: int | None = None
    widgetConfig: WidgetConfig | None = None
    timerLabelDisplay: TimerLabelDisplay = "project_name"
    videoPanelWidthPct: float | None = Field(None, ge=0.0, le=100.0)

    # Tuning overrides — when set, override the corresponding field on
    # DashboardConfig at runtime. Persisted alongside the user's display
    # preferences so they survive dashboard-config replacement.
    confidenceThreshold: float | None = Field(None, ge=0.0, le=1.0)
    labelConfidenceThresholds: dict[int, float] = Field(default_factory=dict)
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

    @field_validator("labelConfidenceThresholds")
    @classmethod
    def _check_label_thresholds(
        cls, value: dict[int, float]
    ) -> dict[int, float]:
        for label_id, threshold in value.items():
            if not 0.0 <= threshold <= 1.0:
                raise ValueError(
                    f"threshold for label {label_id} must be between 0.0 and 1.0"
                )
        return value

    def pruned(
        self, test_case_ids: set[str], label_ids: set[int]
    ) -> "DashboardUserSettings":
        update: dict = {
            "hiddenLabelIds": [
                lid for lid in self.hiddenLabelIds if lid in label_ids
            ],
            "selectedLabelId": (
                self.selectedLabelId
                if self.selectedLabelId in label_ids
                else None
            ),
            "labelConfidenceThresholds": {
                lid: val
                for lid, val in self.labelConfidenceThresholds.items()
                if lid in label_ids
            },
        }
        if self.widgetConfig is not None:
            slots = [
                slot if (slot is None or slot.id in test_case_ids) else None
                for slot in self.widgetConfig.slots
            ]
            update["widgetConfig"] = self.widgetConfig.model_copy(
                update={"slots": slots}
            )
        return self.model_copy(update=update)
