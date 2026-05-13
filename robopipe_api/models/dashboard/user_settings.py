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
    zoneVisible: bool = False
    selectedLabelId: int | None = None
    widgetConfig: WidgetConfig = Field(default_factory=WidgetConfig)
    timerLabelDisplay: TimerLabelDisplay = "project_name"

    def pruned(
        self, test_case_ids: set[str], label_ids: set[int]
    ) -> "DashboardUserSettings":
        slots = [
            slot if (slot is None or slot.id in test_case_ids) else None
            for slot in self.widgetConfig.slots
        ]
        return self.model_copy(
            update={
                "widgetConfig": self.widgetConfig.model_copy(
                    update={"slots": slots}
                ),
                "hiddenLabelIds": [
                    lid for lid in self.hiddenLabelIds if lid in label_ids
                ],
                "selectedLabelId": (
                    self.selectedLabelId
                    if self.selectedLabelId in label_ids
                    else None
                ),
            }
        )
