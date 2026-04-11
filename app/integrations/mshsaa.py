from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import parse_qs, urljoin, urlparse
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
        result = await self.fetch_activity_catalog(school_url)
        return result["activities"]

    async def fetch_activity_catalog(self, school_url: str) -> dict[str, Any]:
        html = await self.fetch_page(school_url)
        activities = self.parse_available_activities(html, school_url)
        if activities:
            return {
                "activities": activities,
                "school_year": self.parse_selected_school_year(html),
                "source_url": school_url,
            }

        schedule_url = self.discover_schedule_url(html, school_url)
        if schedule_url and schedule_url != school_url:
            schedule_html = await self.fetch_page(schedule_url)
            return {
                "activities": self.parse_available_activities(schedule_html, schedule_url),
                "school_year": self.parse_selected_school_year(schedule_html),
                "source_url": schedule_url,
            }
        return {"activities": activities, "school_year": None, "source_url": school_url}

    async def fetch_activity_schedule(self, school_url: str, activity_id: str) -> dict[str, Any]:
        schedule_url = self.build_schedule_url(school_url, activity_id)
        html = await self.fetch_page(schedule_url)
        levels = self.parse_level_labels(html)
        rows = self.parse_schedule_rows(html, schedule_url, levels)
        return {"schedule_url": schedule_url, "levels": levels, "rows": rows}

    def parse_available_activities(self, html: str, base_url: str | None = None) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        activities: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        # The parser deliberately isolates source-specific selectors in one place.
        for option in soup.select("select[name='Activity'] option"):
            value = option.get("value", "").strip()
            label = option.text.strip()
            if value and label:
                key = (value, label)
                if key not in seen:
                    seen.add(key)
                    activities.append({"external_id": value, "name": label})

        activity_scope = soup.select("#Activities a[href*='Schedule.aspx'][href*='alg=']")
        for anchor in activity_scope:
            href = anchor.get("href", "").strip()
            label = self._build_activity_label(anchor)
            external_id = _extract_alg_id(href)
            season_code = anchor.get("data-season", "").strip() or "0"
            level_code = anchor.get("data-level", "").strip() or "9"
            if external_id and label:
                key = (external_id, label)
                if key not in seen:
                    seen.add(key)
                    activities.append(
                        {
                            "external_id": external_id,
                            "name": label,
                            "season_code": season_code,
                            "level_code": level_code,
                            "schedule_url": urljoin(base_url, href) if base_url else href,
                        }
                    )
        activities.sort(key=self._activity_sort_key)
        return activities

    def _build_activity_label(self, anchor) -> str:
        level_prefix = {
            "1": "High School",
            "2": "Junior High",
        }.get(anchor.get("data-level", "").strip(), "")
        parts = [text.strip() for text in anchor.stripped_strings if text.strip()]
        base_label = " ".join(parts)
        if level_prefix and not base_label.lower().startswith(level_prefix.lower()):
            return f"{level_prefix} {base_label}"
        return base_label

    def _activity_sort_key(self, activity: dict[str, str]) -> tuple[int, int, str]:
        season_order = {
            "1": 0,  # Fall
            "2": 1,  # Winter
            "3": 2,  # Spring
            "0": 3,  # Activities / year-round
            "4": 4,  # Emerging
        }.get(activity.get("season_code", "0"), 5)
        level_order = {"1": 0, "2": 1}.get(activity.get("level_code", "9"), 9)
        return (season_order, level_order, activity.get("name", ""))

    def discover_schedule_url(self, html: str, school_url: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.select("a[href*='Schedule.aspx']"):
            href = anchor.get("href", "").strip()
            if href:
                return urljoin(school_url, href)

        parsed = urlparse(school_url)
        query = parse_qs(parsed.query)
        school_id = query.get("s", [None])[0]
        if school_id:
            return urljoin(school_url, f"/MySchool/Schedule.aspx?s={school_id}")
        return None

    def build_schedule_url(self, school_url: str, activity_id: str) -> str:
        parsed = urlparse(school_url)
        school_id = parse_qs(parsed.query).get("s", [None])[0]
        if not school_id:
            raise ValueError("Could not derive the MSHSAA school ID from the configured school URL.")
        return urljoin(school_url, f"/MySchool/Schedule.aspx?s={school_id}&alg={activity_id}")

    def parse_level_labels(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        labels: dict[str, str] = {}
        for item in soup.select("#LevelsOfPlay li[data-level]"):
            level_id = item.get("data-level", "").strip()
            label = " ".join(span.get_text(" ", strip=True) for span in item.select("span.printOnly"))
            if not label:
                label = " ".join(item.stripped_strings)
            if level_id and label:
                labels[level_id] = label
        return labels

    def parse_selected_school_year(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        selected_option = soup.select_one("select[id$='drpYear'] option[selected]")
        if selected_option:
            return selected_option.get_text(" ", strip=True)
        first_option = soup.select_one("select[id$='drpYear'] option")
        if first_option:
            return first_option.get_text(" ", strip=True)
        return None

    def parse_schedule_rows(
        self,
        html: str,
        base_url: str,
        level_labels: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        labels = level_labels or self.parse_level_labels(html)
        rows: list[dict[str, str]] = []
        for row in soup.select("table.schedule tbody tr[data-level]"):
            cells = row.select("td")
            if len(cells) < 4:
                continue

            opponent_cell = row.select_one("td[id$='tdOpponent']")
            score_time_cell = row.select_one("td[id$='tdScoreTime']")
            date_cell = row.select_one("td.gamedate")
            matchup_anchor = row.select_one("td[id$='tdMatchup'] a[href]")
            opponent_link = opponent_cell.select_one("a[href]") if opponent_cell else None
            level_id = row.get("data-level", "").strip()

            rows.append(
                {
                    "date": date_cell.get_text(" ", strip=True) if date_cell else "",
                    "opponent": opponent_cell.get_text(" ", strip=True) if opponent_cell else "",
                    "score_or_time": score_time_cell.get_text(" ", strip=True) if score_time_cell else "",
                    "level_id": level_id,
                    "level_name": labels.get(level_id, level_id or "Unknown"),
                    "row_class": " ".join(row.get("class", [])),
                    "row_type": self._normalize_row_type(row.get("class", [])),
                    "opponent_url": urljoin(base_url, opponent_link.get("href")) if opponent_link else "",
                    "matchup_url": urljoin(base_url, matchup_anchor.get("href")) if matchup_anchor else "",
                }
            )
        return rows

    def _normalize_row_type(self, class_names: list[str]) -> str:
        class_set = set(class_names)
        if "tournament" in class_set:
            return "Tournament"
        if "home" in class_set:
            return "Home"
        if "away" in class_set:
            return "Away"
        if "neutral" in class_set:
            return "Neutral"
        return "Scheduled"

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


def _extract_alg_id(href: str) -> str | None:
    query = parse_qs(urlparse(href).query)
    alg = query.get("alg", [None])[0]
    return str(alg) if alg else None
