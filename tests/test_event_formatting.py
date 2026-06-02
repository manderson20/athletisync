from datetime import UTC, datetime

from app.models import AppSetting, School, SchoolYear, SourceEvent, Sport, SportLevel, SyncMapping
from app.services.event_formatting import build_format_context, render_template, resolve_templates


def test_resolve_templates_prefers_sport_override() -> None:
    settings = AppSetting(
        event_title_template="{school} {sport} vs {opponent}",
        event_description_template="Opponent: {opponent}",
    )
    mapping = SyncMapping(
        school=School(name="Brookfield High School"),
        school_year=SchoolYear(label="2026-2027"),
        sport=Sport(
            name="Golf",
            slug="golf",
            event_title_template_override="{school} {sport} at {location} - {participants}",
            event_description_template_override="Participants: {participants}",
        ),
        level=SportLevel(name="Varsity", slug="varsity"),
    )

    title_template, description_template = resolve_templates(settings, mapping)

    assert title_template == "{school} {sport} at {location} - {participants}"
    assert description_template == "Participants: {participants}"


def test_build_format_context_uses_primary_opponent_and_participants() -> None:
    mapping = SyncMapping(
        school=School(name="Brookfield High School"),
        school_year=SchoolYear(label="2026-2027"),
        sport=Sport(name="Golf", slug="golf"),
        level=SportLevel(name="Varsity", slug="varsity"),
        source_activity_name="High School Golf",
    )
    source_event = SourceEvent(
        title="Golf at Heritage Hills",
        opponent="Moberly, Marceline, Salisbury",
        location="Heritage Hills Golf Club",
        start_at=datetime(2026, 9, 18, 13, 0, tzinfo=UTC),
        payload={
            "activity_name": "High School Golf",
            "school_year_label": "2026-2027",
            "row_type": "Tournament",
            "primary_opponent": "Moberly",
            "participants": "Moberly, Marceline, Salisbury",
        },
    )

    context = build_format_context(mapping, source_event)

    assert context["opponent"] == "Moberly"
    assert context["participants"] == "Moberly, Marceline, Salisbury"
    assert context["event_type"] == "Tournament"
    assert context["location"] == "Heritage Hills Golf Club"


def test_build_format_context_uses_home_away_as_location_fallback() -> None:
    mapping = SyncMapping(
        school=School(name="Brookfield High School"),
        school_year=SchoolYear(label="2026-2027"),
        sport=Sport(name="Football", slug="football"),
        level=SportLevel(name="Varsity", slug="varsity"),
        source_activity_name="High School Football",
    )
    source_event = SourceEvent(
        title="Football vs Central",
        opponent="Central",
        start_at=datetime(2026, 9, 18, 19, 0, tzinfo=UTC),
        payload={
            "activity_name": "High School Football",
            "school_year_label": "2026-2027",
            "row_type": "Home",
        },
    )

    context = build_format_context(mapping, source_event)

    assert context["location"] == "Home"


def test_build_format_context_uses_tbd_when_location_is_unknown() -> None:
    mapping = SyncMapping(
        school=School(name="Brookfield High School"),
        school_year=SchoolYear(label="2026-2027"),
        sport=Sport(name="Music", slug="music"),
        level=SportLevel(name="8th Grade", slug="8th-grade"),
        source_activity_name="Junior High Music",
    )
    source_event = SourceEvent(
        title="Music Event",
        opponent="Brookfield",
        start_at=datetime(2026, 9, 18, 19, 0, tzinfo=UTC),
        payload={
            "activity_name": "Junior High Music",
            "school_year_label": "2026-2027",
            "row_type": "",
        },
    )

    context = build_format_context(mapping, source_event)

    assert context["location"] == "TBD"


def test_build_format_context_formats_human_readable_time_and_sync_timestamp() -> None:
    mapping = SyncMapping(
        school=School(name="Brookfield High School"),
        school_year=SchoolYear(label="2026-2027"),
        sport=Sport(name="Football", slug="football"),
        level=SportLevel(name="Varsity", slug="varsity"),
        source_activity_name="High School Football",
    )
    source_event = SourceEvent(
        title="Football vs Central",
        opponent="Central",
        start_at=datetime(2026, 9, 18, 15, 4, tzinfo=UTC),
        payload={
            "activity_name": "High School Football",
            "school_year_label": "2026-2027",
            "row_type": "Home",
        },
    )

    context = build_format_context(mapping, source_event, "America/Chicago")

    assert context["time"] == "10:04AM"
    assert "T" not in context["last_synced"]
    assert context["last_synced"].endswith("M")


def test_render_template_preserves_description_line_breaks() -> None:
    rendered = render_template(
        "Synced from MSHSAA\nLevel: {level}\nSport: {sport}\nLast Synced: {last_synced}",
        {
            "level": "8th Grade",
            "sport": "Junior High Music",
            "last_synced": "2026-06-02 3:27PM",
        },
    )

    assert rendered == (
        "Synced from MSHSAA\n"
        "Level: 8th Grade\n"
        "Sport: Junior High Music\n"
        "Last Synced: 2026-06-02 3:27PM"
    )
