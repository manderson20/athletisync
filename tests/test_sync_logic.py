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
