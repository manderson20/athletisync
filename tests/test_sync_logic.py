from datetime import datetime

from app.models import AppSetting, School, SchoolYear, Sport, SyncMapping
from app.schemas import MappingFormData
from app.services.sync import SyncService


def test_mapping_form_defaults() -> None:
    payload = MappingFormData(school_year_id=1, school_id=2)
    assert payload.enabled is True
    assert payload.sync_behavior == "standard"


def test_fetch_mapping_events_uses_app_setting_title_template(monkeypatch) -> None:
    mapping = SyncMapping(
        school_year=SchoolYear(label="2026-2027"),
        school=School(name="Central High", mshsaa_url="https://example.org/school"),
        sport=Sport(name="Football", slug="football"),
    )
    settings = AppSetting(event_title_template="{school} {sport}")
    service = SyncService(db=None)  # type: ignore[arg-type]

    monkeypatch.setattr("app.services.sync.discover_and_ensure_school_years", lambda db, labels: None)

    class FakeClient:
        def __init__(self, _settings):
            pass

        async def fetch_activity_catalog(self, _url):
            return {"activities": [{"name": "Football", "external_id": "19"}], "available_school_years": []}

        async def fetch_activity_schedule(self, _url, _activity_id, _year_value=None):
            return {
                "school_year": "2026-2027",
                "rows": [{"date": "09/01", "score_or_time": "7:00 PM", "opponent": "North", "row_type": "game"}],
            }

    monkeypatch.setattr("app.services.sync.MSHSAAClient", FakeClient)

    events = __import__("asyncio").run(service._fetch_mapping_events(mapping, settings))
    assert len(events) == 1
    assert events[0].payload["event_title_template"] == "{school} {sport}"


def test_parse_row_datetime_accepts_ranged_date_text() -> None:
    service = SyncService(db=None)  # type: ignore[arg-type]
    start_at, end_at, is_all_day = service._parse_row_datetime("5/31-12/6", "7:00 PM", "2026-2027")
    assert start_at is not None
    assert start_at.month == 5
    assert start_at.day == 31
    assert is_all_day is False


def test_parse_row_datetime_skips_continuation_marker_rows() -> None:
    service = SyncService(db=None)  # type: ignore[arg-type]
    start_at, end_at, is_all_day = service._parse_row_datetime("⤷ 11", "7:00 PM", "2026-2027")
    assert start_at is None
    assert end_at is None
    assert is_all_day is True


def test_sync_event_key_uses_row_level_name_when_mapping_level_is_blank() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.session import Base
    from app.integrations.mshsaa import build_source_event_key
    from app.models import GoogleCalendar, School, SchoolYear, SourceEvent, Sport, SyncMapping
    from app.schemas import NormalizedEvent

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = Session(engine)
    try:
        school_year = SchoolYear(label="2026-2027")
        school = School(name="Central High")
        sport = Sport(name="Football", slug="football")
        calendar = GoogleCalendar(display_name="Athletics", calendar_id="calendar@example.com")
        mapping = SyncMapping(school_year=school_year, school=school, sport=sport, google_calendar=calendar)
        db.add_all([school_year, school, sport, calendar, mapping])
        db.commit()
        db.refresh(mapping)

        service = SyncService(db)
        run = __import__("app.models", fromlist=["SyncRun"]).SyncRun(trigger="manual", status="running")
        db.add(run)
        db.commit()
        db.refresh(run)

        normalized = NormalizedEvent(
            school_year_label="2026-2027",
            source_reference="ref-1",
            title="Football vs North",
            opponent="North",
            start_at=datetime(2026, 9, 1, 18, 0),
            end_at=datetime(2026, 9, 1, 20, 0),
            payload={"level_name": "Varsity"},
        )

        service._sync_event(
            run,
            mapping,
            normalized,
            __import__("app.services.google_calendar", fromlist=["DryRunCalendarGateway"]).DryRunCalendarGateway(),
            AppSetting(
                event_title_template="{sport} {level} vs {opponent}",
                event_description_template="Opponent: {opponent}",
            ),
        )
        saved = db.query(SourceEvent).one()
        expected_key = build_source_event_key("2026-2027", "Central High", "Football", "Varsity", normalized)
        assert saved.source_event_key == expected_key
    finally:
        db.close()
