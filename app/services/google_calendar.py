from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from app.config import Settings, get_settings
from app.models import AppSetting, GoogleAuthProfile, SourceEvent, SyncMapping
from app.services.event_formatting import build_format_context, render_template, resolve_templates

try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2 import credentials as oauth_credentials
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover - optional dependency
    GoogleAuthRequest = None
    oauth_credentials = None
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
    def __init__(
        self,
        profile: GoogleAuthProfile,
        settings: Settings | None = None,
        app_settings: AppSetting | None = None,
    ) -> None:
        self.profile = profile
        self.settings = settings or get_settings()
        self.app_settings = app_settings

    def _oauth_client_id(self) -> str | None:
        return (
            (self.app_settings.google_oauth_client_id if self.app_settings else None)
            or self.settings.google_oauth_client_id
        )

    def _oauth_client_secret(self) -> str | None:
        return (
            (self.app_settings.google_oauth_client_secret if self.app_settings else None)
            or self.settings.google_oauth_client_secret
        )

    def _build_service(self):
        if build is None:
            raise RuntimeError("Install AthletiSync with the google extra to enable Google Calendar sync.")

        credentials = self._build_credentials()
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _build_credentials(self):
        if self.profile.auth_type == "oauth":
            if oauth_credentials is None:
                raise RuntimeError("Install AthletiSync with the google extra to enable Google Calendar sync.")
            if GoogleAuthRequest is None:
                raise RuntimeError("Install AthletiSync with the google extra to enable Google Calendar sync.")
            client_id = self._oauth_client_id()
            client_secret = self._oauth_client_secret()
            if not client_id or not client_secret:
                raise RuntimeError("Missing Google OAuth client settings.")
            if not self.profile.oauth_refresh_token:
                raise RuntimeError("OAuth profile is missing a refresh token.")

            scopes = (
                self.profile.oauth_scopes.split()
                if self.profile.oauth_scopes
                else ["https://www.googleapis.com/auth/calendar"]
            )
            credentials = oauth_credentials.Credentials(
                token=None,
                refresh_token=self.profile.oauth_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=scopes,
            )
            credentials.refresh(GoogleAuthRequest())
            return credentials

        if service_account is None:
            raise RuntimeError("Install AthletiSync with the google extra to enable Google Calendar sync.")
        if not self.profile.service_account_json:
            raise RuntimeError("Service account profile is missing JSON credentials.")

        creds_info = json.loads(self.profile.service_account_json)
        return service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )

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
        if self.profile.auth_type == "oauth":
            label = self.profile.oauth_account_email or self.profile.name
            return True, f"OAuth connection succeeded for {label}."
        return True, "Service account connection succeeded."

    def test_calendar_access(self, calendar_id: str) -> tuple[bool, str]:
        service = self._build_service()
        entry = service.calendarList().get(calendarId=calendar_id).execute()
        access_role = entry.get("accessRole", "unknown")
        ok = access_role in {"owner", "writer"}
        if ok:
            return True, f"Calendar access confirmed with role: {access_role}."
        return False, f"Calendar access is {access_role}. AthletiSync needs owner or writer access."


class DryRunCalendarGateway:
    def upsert_event(self, calendar_id: str, event_id: str | None, payload: CalendarEventPayload) -> str:
        base = event_id or f"{calendar_id}-{payload.summary}"
        return sha256(base.encode("utf-8")).hexdigest()[:24]

    def test_connection(self) -> tuple[bool, str]:
        return True, "Dry-run calendar gateway is active."

    def test_calendar_access(self, calendar_id: str) -> tuple[bool, str]:
        return True, f"Dry-run calendar gateway is active for {calendar_id}."


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


def build_event_payload(mapping: SyncMapping, source_event: SourceEvent, settings: AppSetting | str) -> CalendarEventPayload:
    context = build_format_context(mapping, source_event)
    if isinstance(settings, AppSetting):
        title_template, description_template = resolve_templates(settings, mapping)
    else:
        payload = source_event.payload if isinstance(source_event.payload, dict) else {}
        title_template = payload.get("event_title_template") or source_event.title
        description_template = settings
    description = render_template(description_template, context)
    summary = render_template(title_template or "{sport}", context)
    if source_event.is_all_day:
        start = {"date": source_event.start_at.date().isoformat()} if source_event.start_at else {}
        end = {"date": (source_event.end_at or source_event.start_at).date().isoformat()} if source_event.start_at else {}
    else:
        start = {"dateTime": source_event.start_at.isoformat()} if source_event.start_at else {}
        end = {"dateTime": (source_event.end_at or source_event.start_at).isoformat()} if source_event.start_at else {}

    status = "cancelled" if source_event.status == "cancelled" else "confirmed"
    return CalendarEventPayload(
        summary=summary or source_event.title,
        description=description,
        location=source_event.location,
        start=start,
        end=end,
        status=status,
    )
