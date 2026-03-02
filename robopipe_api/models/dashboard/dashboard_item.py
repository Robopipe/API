from enum import Enum

from ..base_model import BaseModel
from .label import Label


class DashboardItemType(str, Enum):
    CHECK = "CHECK"
    DEFECT = "DEFECT"


class DashboardItemSeverity(str, Enum):
    ALERT = "ALERT"
    WARNING = "WARNING"


class DashboardItemPosition(str, Enum):
    POS_LEFT = "POS_LEFT"
    POS_RIGHT = "POS_RIGHT"
    POS_TOP = "POS_TOP"
    POS_BOTTOM = "POS_BOTTOM"
    POS_CENTER = "POS_CENTER"
    AREA = "AREA"
    COUNT = "COUNT"


class DashboardItemLimitUnit(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    COUNT = "COUNT"


class DashboardItem(BaseModel):
    id: int
    name: str
    type: DashboardItemType
    severity: DashboardItemSeverity
    position: DashboardItemPosition
    unit: DashboardItemLimitUnit
    targetLabel: Label
    targetParentLabel: Label | None = None
    limitFrom: float | None = None
    limitTo: float | None = None
