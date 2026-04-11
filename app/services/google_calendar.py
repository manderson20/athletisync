from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from app.models import GoogleAuthProfile, SourceEvent, SyncMapping

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover - optional dependency
    service_account = None
    build = None


@dataclass
class CalendarEventPayload:
    summary: str
    description: str
    location: str | None
    start: dict
    end: dict
    status: str = "confirmed"


class CalendarGateway(Protocol):
    def upsert_event(self, calendar_id: str, event_id: str | None, payload: CalendarEventPayload) -> str: ...

    def test_connection(self) -> tuple[bool, str]: ...


class GoogleCalendarGateway:
    def __init__(self, profile: GoogleAuthProfile) -> None:
        self.profile = profile

    def _build_service(self):
        if service_account is None or build is None:
            raise RuntimeError("Install AthletiSync with the google extra to enable Google Calendar sync.")

        creds_info = json.loads(self.profile.service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def upsert_event(self, calendar_id: str, event_id: str | None, payload: CalendarEventPayload) -> str:
        service = self._build_service()
        body = {
            "summary": payload.summary,
            "description": payload.description,
            "location": payload.location,
            "start": payload.start,
            "end": payload.end,
            "status": payload.status,
        }
        if event_id:
            result = service.events().update(calendarId=calendar_id, eventId=event_id, body=body).execute()
        else:
            result = service.events().insert(calendarId=calendar_id, body=body).execute()
        return result["id"]

    def test_connection(self) -> tuple[bool, str]:
        service = self._build_service()
        service.calendarList().list(maxResults=1).execute()
        return True, "Connection succeeded."


class DryRunCalendarGateway:
    def upsert_event(self, calendar_id: str, event_id: str | None, payload: CalendarEventPayload) -> str:
        base = event_id or f"{calendar_id}-{payload.summary}"
        return sha256(base.encode("utf-8")).hexdigest()[:24]

    def test_connection(self) -> tuple[bool, str]:
        return True, "Dry-run calendar gateway is active."


def event_fingerprint(source_event: SourceEvent) -> str:
    parts = [
        source_event.title,
        source_event.opponent or "",
        source_event.location or "",
        source_event.status,
        source_event.start_at.isoformat() if source_event.start_at else "",
        source_event.end_at.isoformat() if source_event.end_at else "",
    ]
    return sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_event_payload(mapping: SyncMapping, source_event: SourceEvent, description_template: str) -> CalendarEventPayload:
    description = description_template.format(
        school=mapping.school.name,
        sport=mapping.sport.name if mapping.sport else "General",
        level=mapping.level.name if mapping.level else "General",
        school_year=mapping.school_year.label,
        opponent=source_event.opponent or "TBD",
        location=source_event.location or "TBD",
        last_synced=datetime.now(UTC).isoformat(),
    )
    if source_event.is_all_day:
        start = {"date": source_event.start_at.date().isoformat()} if source_event.start_at else {}
        end = {"date": (source_event.end_at or source_event.start_at).date().isoformat()} if source_event.start_at else {}
    else:
        start = {"dateTime": source_event.start_at.isoformat()} if source_event.start_at else {}
        end = {"dateTime": (source_event.end_at or source_event.start_at).isoformat()} if source_event.start_at else {}

    status = "cancelled" if source_event.status == "cancelled" else "confirmed"
    return CalendarEventPayload(
        summary=source_event.title,
        description=description,
        location=source_event.location,
        start=start,
        end=end,
        status=status,
    )
