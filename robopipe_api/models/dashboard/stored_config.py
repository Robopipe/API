from ..base_model import BaseModel
from .dashboard_config import DashboardConfig
from ..nn_config import NNConfig


class StoredConfigSummary(BaseModel):
    config_id: int
    config_name: str


class StoredDashboardConfig(BaseModel):
    config_id: int
    config_name: str
    dashboard_config: DashboardConfig
    nn_config: NNConfig
    model_path: str
