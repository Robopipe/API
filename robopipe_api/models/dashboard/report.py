from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    Field,
    PlainSerializer,
    field_serializer,
)

from ...dashboard.reports_store import _format_utc_z


ReportStatus = Literal["pending", "running", "completed", "failed"]


def _coerce_utc(value: datetime | str | None) -> datetime | None:
    """Accept SQLite's naive 'YYYY-MM-DD HH:MM:SS' strings as UTC."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


UtcTimestamp = Annotated[
    AwareDatetime,
    BeforeValidator(_coerce_utc),
    PlainSerializer(_format_utc_z, return_type=str),
]


class CreateReportRequest(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    session_id: int | None = None
    event_ids: list[int] | None = Field(default=None, min_length=1)


class DashboardReportSummary(BaseModel):
    id: int
    dashboard_id: int
    created_at: AwareDatetime
    filter_start: AwareDatetime | None = None
    filter_end: AwareDatetime | None = None
    session_id: int | None = None
    event_ids: list[int] | None = None
    status: ReportStatus
    error: str | None = None

    @field_serializer("created_at", "filter_start", "filter_end")
    def serialize_utc_z(self, value: AwareDatetime | None) -> str | None:
        return _format_utc_z(value)


class SessionSummary(BaseModel):
    id: int
    start_time: UtcTimestamp
    end_time: UtcTimestamp | None = None
    end_reason: str | None = None
    event_count: int
    failed_count: int


class ViolatedLimit(BaseModel):
    limit_id: str
    limit_name: str
    display_id: int | None = None
    parent_display_id: int | None = None


class EventListItem(BaseModel):
    id: int
    session_id: int
    session_start: UtcTimestamp
    session_end: UtcTimestamp | None = None
    model_id: int | None = None
    model_name: str | None = None
    timestamp: UtcTimestamp
    test_case_id: str
    test_case_name: str
    passed: bool
    has_picture: bool
    violated_limits: list[ViolatedLimit]


class EventListResponse(BaseModel):
    items: list[EventListItem]
    total: int
    limit: int
    offset: int


class EventDetection(BaseModel):
    label_id: int
    label_name: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    display_id: int | None = None
    parent_display_id: int | None = None
    role: str | None = None


class EventDetail(EventListItem):
    detections: list[EventDetection]
