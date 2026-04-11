from datetime import UTC, datetime

from app.integrations.mshsaa import MSHSAAClient, build_source_event_key
from app.config import Settings


def test_normalize_schedule_payload() -> None:
    client = MSHSAAClient(Settings())
    events = client.normalize_schedule_payload(
        {
            "events": [
                {
                    "id": "evt-1",
                    "title": "Football vs North",
                    "opponent": "North",
                    "location": "Stadium",
                    "start": "2026-09-01T18:00:00Z",
                    "end": "2026-09-01T20:00:00Z",
                }
            ]
        }
    )

    assert len(events) == 1
    assert events[0].title == "Football vs North"
    assert events[0].start_at == datetime(2026, 9, 1, 18, 0, tzinfo=UTC)


def test_source_event_key_is_stable() -> None:
    client = MSHSAAClient(Settings())
    event = client.normalize_schedule_payload(
        {
            "events": [
                {
                    "id": "evt-2",
                    "title": "Volleyball Tournament",
                    "start": "2026-09-02T09:00:00Z",
                }
            ]
        }
    )[0]

    key_one = build_source_event_key("2026-2027", "Central", "Volleyball", "Varsity", event)
    key_two = build_source_event_key("2026-2027", "Central", "Volleyball", "Varsity", event)

    assert key_one == key_two
