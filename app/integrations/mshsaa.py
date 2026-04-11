from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.schemas import NormalizedEvent


class MSHSAAClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_page(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def fetch_available_activities(self, school_url: str) -> list[dict[str, str]]:
        html = await self.fetch_page(school_url)
        soup = BeautifulSoup(html, "html.parser")
        activities: list[dict[str, str]] = []

        # The parser deliberately isolates source-specific selectors in one place.
        for option in soup.select("select[name='Activity'] option"):
            value = option.get("value", "").strip()
            label = option.text.strip()
            if value and label:
                activities.append({"external_id": value, "name": label})
        return activities

    def normalize_schedule_payload(self, payload: dict[str, Any]) -> list[NormalizedEvent]:
        events: list[NormalizedEvent] = []
        for raw_event in payload.get("events", []):
            start_at = _parse_datetime(raw_event.get("start"))
            end_at = _parse_datetime(raw_event.get("end"))
            events.append(
                NormalizedEvent(
                    source_reference=str(raw_event.get("id") or ""),
                    title=raw_event.get("title") or "Untitled Event",
                    opponent=raw_event.get("opponent"),
                    location=raw_event.get("location"),
                    start_at=start_at,
                    end_at=end_at,
                    is_all_day=bool(raw_event.get("all_day", False)),
                    status=(raw_event.get("status") or "scheduled").lower(),
                    payload=raw_event,
                )
            )
        return events


def build_source_event_key(
    school_year: str,
    school: str,
    sport: str,
    level: str,
    event: NormalizedEvent,
) -> str:
    raw = "|".join(
        [
            school_year,
            school,
            sport,
            level,
            event.source_reference or "",
            event.title,
            event.opponent or "",
            event.location or "",
            event.start_at.isoformat() if event.start_at else "",
        ]
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
