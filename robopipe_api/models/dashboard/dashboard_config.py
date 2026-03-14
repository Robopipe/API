from enum import Enum

from pydantic import ConfigDict

from ..base_model import BaseModel
from .dashboard_item import DashboardItem
from .label import Label


class DashboardLineDirection(str, Enum):
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    lineDirection: DashboardLineDirection
    linePosition: float
    items: list[DashboardItem]
    labels: list[Label]
    remoteBackendUrl: str | None = None
