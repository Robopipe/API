from datetime import datetime
from typing import Literal

from pydantic import BaseModel


ReportStatus = Literal["pending", "running", "completed", "failed"]


class CreateReportRequest(BaseModel):
    start: datetime | None = None
    end: datetime | None = None


class DashboardReportSummary(BaseModel):
    id: int
    dashboard_id: int
    created_at: datetime
    filter_start: datetime | None = None
    filter_end: datetime | None = None
    status: ReportStatus
    error: str | None = None
