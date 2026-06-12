from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, field_serializer

from ...dashboard.reports_store import _format_utc_z


ReportStatus = Literal["pending", "running", "completed", "failed"]


class CreateReportRequest(BaseModel):
    start: datetime | None = None
    end: datetime | None = None


class DashboardReportSummary(BaseModel):
    id: int
    dashboard_id: int
    created_at: AwareDatetime
    filter_start: AwareDatetime | None = None
    filter_end: AwareDatetime | None = None
    status: ReportStatus
    error: str | None = None

    @field_serializer("created_at", "filter_start", "filter_end")
    def serialize_utc_z(self, value: AwareDatetime | None) -> str | None:
        return _format_utc_z(value)
