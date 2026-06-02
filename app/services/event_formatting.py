from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import re
from zoneinfo import ZoneInfo

from app.models import AppSetting, SourceEvent, SyncMapping


def build_format_context(
    mapping: SyncMapping,
    source_event: SourceEvent,
    timezone_name: str | None = None,
) -> dict[str, str]:
    payload = source_event.payload if isinstance(source_event.payload, dict) else {}
    school_year_label = payload.get("school_year_label") or mapping.school_year.label
    start_at = _display_datetime(source_event.start_at, timezone_name)
    participants = _value(payload.get("participants") or source_event.opponent)
    row_type = _value(payload.get("row_type"))
    opponent = _value(payload.get("primary_opponent") or source_event.opponent)

    if row_type == "Tournament" and not opponent:
        opponent = "Tournament"

    return {
        "district": "",
        "school": _value(mapping.school.name),
        "sport": _value(mapping.sport.name if mapping.sport else payload.get("activity_name")),
        "level": _display_level(mapping.level.name if mapping.level else payload.get("level_name")),
        "activity": _value(payload.get("activity_name") or mapping.source_activity_name or mapping.sport.name if mapping.sport else ""),
        "opponent": opponent,
        "participants": participants,
        "location": _display_location(source_event.location, row_type),
        "school_year": _value(school_year_label),
        "date": _value(start_at.strftime("%Y-%m-%d") if start_at else ""),
        "time": _value(_format_clock_time(start_at) if start_at and not source_event.is_all_day else ""),
        "event_type": row_type,
        "last_synced": _format_sync_timestamp(datetime.now(UTC), timezone_name),
    }


def render_template(template: str, context: dict[str, str]) -> str:
    safe_context = defaultdict(str, context)
    rendered = template.format_map(safe_context).strip()
    normalized_lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in rendered.splitlines()]
    return "\n".join(normalized_lines).strip()


def preview_event_format(settings: AppSetting) -> dict[str, list[dict[str, str]]]:
    scenarios = []
    for name, sample_mapping, sample_event in _sample_preview_scenarios():
        title_template, description_template = resolve_templates(settings, sample_mapping)
        context = build_format_context(sample_mapping, sample_event, settings.timezone)
        scenarios.append(
            {
                "label": name,
                "title": render_template(title_template, context),
                "description": render_template(description_template, context),
            }
        )
    return {"scenarios": scenarios}


def resolve_templates(settings: AppSetting, mapping: SyncMapping) -> tuple[str, str]:
    sport = mapping.sport
    title_template = settings.event_title_template
    description_template = settings.event_description_template
    if sport and sport.event_title_template_override:
        title_template = sport.event_title_template_override
    if sport and sport.event_description_template_override:
        description_template = sport.event_description_template_override
    return title_template, description_template


def _sample_mapping(
    sport_name: str = "Football",
    level_name: str = "Varsity",
    title_override: str | None = None,
    description_override: str | None = None,
) -> SyncMapping:
    from app.models import School, SchoolYear, Sport, SportLevel, SyncMapping

    return SyncMapping(
        school=School(name="Brookfield High School"),
        school_year=SchoolYear(label="2026-2027"),
        sport=Sport(
            name=sport_name,
            slug=sport_name.lower().replace(" ", "-"),
            event_title_template_override=title_override,
            event_description_template_override=description_override,
        ),
        level=SportLevel(name=level_name, slug=level_name.lower().replace(" ", "-")),
        source_activity_name=f"High School {sport_name}",
    )


def _sample_event(
    title: str = "Football vs Central",
    opponent: str = "Central",
    location: str = "",
    row_type: str = "Home",
    activity_name: str = "High School Football",
) -> SourceEvent:
    from app.models import SourceEvent

    return SourceEvent(
        title=title,
        opponent=opponent,
        location=location,
        start_at=datetime(2026, 9, 18, 19, 0),
        is_all_day=False,
        payload={"activity_name": activity_name, "school_year_label": "2026-2027", "row_type": row_type},
    )


def _sample_preview_scenarios() -> list[tuple[str, SyncMapping, SourceEvent]]:
    return [
        (
            "Standard Matchup",
            _sample_mapping("Football", "Varsity"),
            _sample_event(),
        ),
        (
            "Tournament",
            _sample_mapping("Volleyball", "Varsity"),
            _sample_event(
                title="Volleyball Tournament",
                opponent="Moberly, Kirksville, Hannibal",
                location="Moberly High School",
                row_type="Tournament",
                activity_name="High School Volleyball",
            ),
        ),
        (
            "Multi-Team Event",
            _sample_mapping(
                "Golf",
                "Varsity",
                title_override="{school} {sport} {level} at {location} - {participants}",
            ),
            _sample_event(
                title="Golf at Country Club",
                opponent="Moberly, Marceline, Salisbury",
                location="Heritage Hills Golf Club",
                row_type="Scheduled",
                activity_name="High School Golf",
            ),
        ),
    ]


def _value(value: str | None) -> str:
    return value or ""


def _display_location(location: str | None, row_type: str) -> str:
    if location and location.strip():
        return location.strip()
    if row_type in {"Home", "Away", "Neutral"}:
        return row_type
    return "TBD"


def _display_level(level_name: str | None) -> str:
    normalized = _value(level_name).strip()
    if normalized == "Junior High":
        return "Middle School"
    if normalized == "Junior Varsity":
        return "JV"
    return normalized


def _format_clock_time(value: datetime) -> str:
    return value.strftime("%I:%M%p").lstrip("0")


def _format_sync_timestamp(value: datetime, timezone_name: str | None) -> str:
    display_value = _display_datetime(value, timezone_name)
    return f"{display_value.strftime('%Y-%m-%d')} {display_value.strftime('%I:%M%p').lstrip('0')}"


def _display_datetime(value: datetime | None, timezone_name: str | None) -> datetime | None:
    if value is None:
        return None
    if not timezone_name:
        return value

    target_tz = ZoneInfo(timezone_name)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).astimezone(target_tz)
    return value.astimezone(target_tz)
