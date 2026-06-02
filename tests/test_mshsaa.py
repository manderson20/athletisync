from datetime import UTC, datetime

from app.integrations.mshsaa import (
    MSHSAAClient,
    build_source_event_key,
    extract_stable_event_reference,
    row_has_schedulable_date,
)
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


def test_source_event_key_prefers_stable_reference_over_mutable_fields() -> None:
    client = MSHSAAClient(Settings())
    original = client.normalize_schedule_payload(
        {
            "events": [
                {
                    "id": "https://www.mshsaa.org/MySchool/Matchup.aspx?s=244&alg=19&comp=2708571",
                    "title": "Football vs Monroe City",
                    "opponent": "Monroe City",
                    "start": "2026-08-28T19:00:00Z",
                }
            ]
        }
    )[0]
    changed = client.normalize_schedule_payload(
        {
            "events": [
                {
                    "id": "https://www.mshsaa.org/MySchool/Matchup.aspx?s=244&alg=19&comp=2708571",
                    "title": "Football vs Monroe City - Weather Make-up",
                    "opponent": "Monroe City",
                    "start": "2026-08-29T16:00:00Z",
                }
            ]
        }
    )[0]

    key_one = build_source_event_key("2026-2027", "Central", "Football", "Varsity", original)
    key_two = build_source_event_key("2026-2027", "Central", "Football", "Varsity", changed)

    assert key_one == key_two


def test_parse_available_activities() -> None:
    client = MSHSAAClient(Settings())
    activities = client.parse_available_activities(
        """
        <html>
          <body>
            <select name="Activity">
              <option value="">Select</option>
              <option value="1">Football</option>
              <option value="2">Volleyball</option>
            </select>
          </body>
        </html>
        """
    )

    assert activities == [
        {"external_id": "1", "name": "Football"},
        {"external_id": "2", "name": "Volleyball"},
    ]


def test_parse_available_activities_from_schedule_links() -> None:
    client = MSHSAAClient(Settings())
    activities = client.parse_available_activities(
        """
        <html>
          <body>
            <div id="Activities">
              <a href="/MySchool/Schedule.aspx?s=244&alg=14" data-level="1" data-season="1">Football <span>Fall Season</span></a>
              <a href="/MySchool/Schedule.aspx?s=244&alg=38" data-level="2" data-season="1">Softball <span>Fall Season</span></a>
            </div>
          </body>
        </html>
        """,
        "https://www.mshsaa.org/MySchool/Schedule.aspx?s=244",
    )

    assert activities == [
        {
            "external_id": "14",
            "name": "High School Football Fall Season",
            "season_code": "1",
            "level_code": "1",
            "schedule_url": "https://www.mshsaa.org/MySchool/Schedule.aspx?s=244&alg=14",
        },
        {
            "external_id": "38",
            "name": "Junior High Softball Fall Season",
            "season_code": "1",
            "level_code": "2",
            "schedule_url": "https://www.mshsaa.org/MySchool/Schedule.aspx?s=244&alg=38",
        },
    ]


def test_parse_schedule_rows_and_levels() -> None:
    client = MSHSAAClient(Settings())
    html = """
    <html>
      <body>
        <ul id="LevelsOfPlay" class="myschoolnav">
          <li data-level="7" class="level current"><a><span class="printOnly">Junior High</span></a></li>
          <li data-level="5" class="level"><a><span class="printOnly">8th Grade</span></a></li>
        </ul>
        <table class="schedule">
          <tbody>
            <tr data-level="7" class="home">
              <td></td>
              <td class="gamedate top">9/15</td>
              <td id="x_tdOpponent" class="top"><a href="/foo">Salisbury</a></td>
              <td id="x_tdScoreTime" class="center">6:00 PM</td>
              <td id="x_tdMatchup"><a href="/matchup">Matchup</a></td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    levels = client.parse_level_labels(html)
    rows = client.parse_schedule_rows(html, "https://www.mshsaa.org/MySchool/Schedule.aspx?s=244&alg=14", levels)

    assert levels == {"7": "Junior High", "5": "8th Grade"}
    assert rows == [
        {
            "date": "9/15",
            "opponent": "Salisbury",
            "score_or_time": "6:00 PM",
            "level_id": "7",
            "level_name": "Junior High",
            "row_class": "home",
            "row_type": "Home",
            "opponent_url": "https://www.mshsaa.org/foo",
            "matchup_url": "https://www.mshsaa.org/matchup",
            "stable_reference": None,
        }
    ]


def test_parse_selected_school_year() -> None:
    client = MSHSAAClient(Settings())
    year = client.parse_selected_school_year(
        """
        <select id="ctl00_contentMain_drpYear">
          <option value="2026">2026-2027</option>
          <option selected="selected" value="2025">2025-2026</option>
        </select>
        """
    )

    assert year == "2025-2026"


def test_parse_available_school_years() -> None:
    client = MSHSAAClient(Settings())
    years = client.parse_available_school_years(
        """
        <select id="ctl00_contentMain_drpYear">
          <option value="2027">2027-2028</option>
          <option value="2026">2026-2027</option>
          <option selected="selected" value="2025">2025-2026</option>
        </select>
        """
    )

    assert years == ["2027-2028", "2026-2027", "2025-2026"]


def test_extract_stable_event_reference() -> None:
    assert (
        extract_stable_event_reference("https://www.mshsaa.org/MySchool/Matchup.aspx?s=244&alg=19&comp=2708571")
        == "comp:2708571"
    )
    assert (
        extract_stable_event_reference("https://www.mshsaa.org/MySchool/Tournament.aspx?s=244&alg=19&tournament=573131")
        == "tournament:573131"
    )
    assert extract_stable_event_reference("https://www.mshsaa.org/MySchool/Schedule.aspx?s=134&alg=19&year=2026") is None


def test_row_has_schedulable_date_requires_a_real_month_day_value() -> None:
    assert row_has_schedulable_date({"date": "9/15"}) is True
    assert row_has_schedulable_date({"date": "5/31-12/6"}) is True
    assert row_has_schedulable_date({"date": "⤷ 11"}) is False
    assert row_has_schedulable_date({"date": ""}) is False
