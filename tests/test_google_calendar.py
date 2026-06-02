from datetime import datetime

from app.models import AppSetting, School, SchoolYear, SourceEvent, Sport, SportLevel, SyncMapping
from app.services.google_calendar import build_event_payload, event_fingerprint


def test_event_fingerprint_changes_when_title_changes() -> None:
    event = SourceEvent(title="Game A", status="scheduled")
    original = event_fingerprint(event)
    event.title = "Game B"
    assert event_fingerprint(event) != original


def test_build_event_payload_contains_mapping_metadata() -> None:
    mapping = SyncMapping(
        school_year=SchoolYear(label="2026-2027"),
        school=School(name="Central High"),
        sport=Sport(name="Football", slug="football"),
        level=SportLevel(name="Varsity", slug="varsity"),
    )
    source_event = SourceEvent(
        title="Football vs North",
        opponent="North",
        location="Stadium",
        start_at=datetime(2026, 9, 1, 18, 0),
        end_at=datetime(2026, 9, 1, 20, 0),
        status="scheduled",
    )
    payload = build_event_payload(
        mapping,
        source_event,
        "School: {school} Sport: {sport} Level: {level} School Year: {school_year}",
    )

    assert payload.summary == "Football vs North"
    assert "Central High" in payload.description


def test_build_event_payload_includes_timezone_for_timed_events() -> None:
    mapping = SyncMapping(
        school_year=SchoolYear(label="2026-2027"),
        school=School(name="Central High"),
        sport=Sport(name="Football", slug="football"),
    )
    source_event = SourceEvent(
        title="Football vs North",
        opponent="North",
        start_at=datetime.fromisoformat("2026-09-01T18:00:00-05:00"),
        end_at=datetime.fromisoformat("2026-09-01T20:00:00-05:00"),
        status="scheduled",
        payload={"level_name": "Varsity"},
    )
    settings = AppSetting(
        timezone="America/Chicago",
        event_title_template="{sport} {level} vs {opponent}",
        event_description_template="Opponent: {opponent}",
    )

    payload = build_event_payload(mapping, source_event, settings)
    assert payload.summary == "Football Varsity vs North"
    assert payload.start["timeZone"] == "America/Chicago"
    assert payload.end["timeZone"] == "America/Chicago"
