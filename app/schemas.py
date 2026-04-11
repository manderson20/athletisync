from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginFormData(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=255)


class SettingsFormData(BaseModel):
    district_name: str
    timezone: str
    polling_interval_minutes: int = Field(ge=5, le=1440)
    default_school_year_label: str
    cancellation_behavior: str
    sync_retry_count: int = Field(ge=0, le=10)
    log_retention_days: int = Field(ge=1, le=365)


class MappingFormData(BaseModel):
    school_year_id: int
    school_id: int
    sport_id: int | None = None
    level_id: int | None = None
    google_calendar_id: int | None = None
    enabled: bool = True
    sync_behavior: str = "standard"
    notes: str | None = None


class NormalizedEvent(BaseModel):
    source_reference: str | None = None
    title: str
    opponent: str | None = None
    location: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    is_all_day: bool = False
    status: str = "scheduled"
    payload: dict = Field(default_factory=dict)


class SyncOutcome(BaseModel):
    action: str
    status: str
    message: str
