from typing import Literal

from pydantic import Field

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


class DashboardUserSettings(BaseModel):
    displayMode: DetectionDisplayMode = "all"
    multiLimitMode: MultiLimitDisplayMode = "highest"
    hiddenLabelIds: list[int] = []
    zoneVisible: bool = True
    selectedLabelId: int | None = None
    widgetConfig: WidgetConfig = Field(default_factory=WidgetConfig)
    timerLabelDisplay: TimerLabelDisplay = "project_name"
