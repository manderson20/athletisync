from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    district_name: Mapped[str] = mapped_column(String(255), default="AthletiSync District")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Chicago")
    polling_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    default_school_year_label: Mapped[str] = mapped_column(String(16), default="2025-2026")
    event_title_template: Mapped[str] = mapped_column(
        Text,
        default="{school} {sport} {level} vs {opponent}",
    )
    event_description_template: Mapped[str] = mapped_column(
        Text,
        default=(
            "Synced from MSHSAA\n"
            "School: {school}\n"
            "Sport: {sport}\n"
            "Level: {level}\n"
            "School Year: {school_year}\n"
            "Opponent: {opponent}\n"
            "Location: {location}\n"
            "Last Synced: {last_synced}"
        ),
    )
    cancellation_behavior: Mapped[str] = mapped_column(String(32), default="mark_cancelled")
    sync_retry_count: Mapped[int] = mapped_column(Integer, default=2)
    log_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    google_oauth_client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_oauth_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_oauth_redirect_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SchoolYear(Base):
    __tablename__ = "school_years"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(16), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    mappings: Mapped[list["SyncMapping"]] = relationship(back_populates="school_year")


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    mshsaa_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    mappings: Mapped[list["SyncMapping"]] = relationship(back_populates="school")


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    event_title_template_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_description_template_override: Mapped[str | None] = mapped_column(Text, nullable=True)

    mappings: Mapped[list["SyncMapping"]] = relationship(back_populates="sport")


class SportLevel(Base):
    __tablename__ = "sport_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)

    mappings: Mapped[list["SyncMapping"]] = relationship(back_populates="level")


class GoogleAuthProfile(Base):
    __tablename__ = "google_auth_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    auth_type: Mapped[str] = mapped_column(String(32), default="service_account")
    service_account_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    calendars: Mapped[list["GoogleCalendar"]] = relationship(back_populates="auth_profile")


class GoogleCalendar(Base):
    __tablename__ = "google_calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auth_profile_id: Mapped[int | None] = mapped_column(ForeignKey("google_auth_profiles.id"))
    calendar_id: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    auth_profile: Mapped[GoogleAuthProfile | None] = relationship(back_populates="calendars")
    mappings: Mapped[list["SyncMapping"]] = relationship(back_populates="google_calendar")


class SyncMapping(Base):
    __tablename__ = "sync_mappings"
    __table_args__ = (
        UniqueConstraint(
            "school_year_id",
            "school_id",
            "sport_id",
            "level_id",
            "google_calendar_id",
            name="uq_mapping_dimension",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_year_id: Mapped[int] = mapped_column(ForeignKey("school_years.id"))
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    sport_id: Mapped[int | None] = mapped_column(ForeignKey("sports.id"), nullable=True)
    level_id: Mapped[int | None] = mapped_column(ForeignKey("sport_levels.id"), nullable=True)
    google_calendar_id: Mapped[int | None] = mapped_column(ForeignKey("google_calendars.id"), nullable=True)
    source_activity_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_activity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_behavior: Mapped[str] = mapped_column(String(32), default="standard")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    school_year: Mapped[SchoolYear] = relationship(back_populates="mappings")
    school: Mapped[School] = relationship(back_populates="mappings")
    sport: Mapped[Sport | None] = relationship(back_populates="mappings")
    level: Mapped[SportLevel | None] = relationship(back_populates="mappings")
    google_calendar: Mapped[GoogleCalendar | None] = relationship(back_populates="mappings")
    source_events: Mapped[list["SourceEvent"]] = relationship(back_populates="mapping")


class SourceEvent(Base):
    __tablename__ = "source_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mapping_id: Mapped[int] = mapped_column(ForeignKey("sync_mappings.id"))
    source_event_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    opponent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    mapping: Mapped[SyncMapping] = relationship(back_populates="source_events")
    synced_event: Mapped["SyncedEvent | None"] = relationship(back_populates="source_event")


class SyncedEvent(Base):
    __tablename__ = "synced_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_event_id: Mapped[int] = mapped_column(ForeignKey("source_events.id"), unique=True)
    google_event_id: Mapped[str] = mapped_column(String(255))
    calendar_id: Mapped[str] = mapped_column(String(255))
    fingerprint: Mapped[str] = mapped_column(String(64))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    source_event: Mapped[SourceEvent] = relationship(back_populates="synced_event")


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)

    items: Mapped[list["SyncRunItem"]] = relationship(back_populates="sync_run")


class SyncRunItem(Base):
    __tablename__ = "sync_run_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("sync_runs.id"))
    source_event_key: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    sync_run: Mapped[SyncRun] = relationship(back_populates="items")
