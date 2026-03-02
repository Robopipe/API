from pydantic import ConfigDict

from ..base_model import BaseModel
from .dashboard_item import DashboardItem
from .label import Label


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    items: list[DashboardItem]
    labels: list[Label]
