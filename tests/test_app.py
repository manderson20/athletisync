from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient


def build_test_client() -> TestClient:
    from app.config import get_settings

    get_settings.cache_clear()

    from app.db.session import Base, SessionLocal, engine
    from app.services.bootstrap import bootstrap_defaults

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap_defaults(db, get_settings())
    finally:
        db.close()

    from app.main import create_app

    return TestClient(create_app())


def extract_csrf(response_text: str) -> str:
    marker = 'name="csrf_token" value="'
    start = response_text.index(marker) + len(marker)
    end = response_text.index('"', start)
    return response_text[start:end]


def login(client: TestClient) -> None:
    login_page = client.get("/login")
    csrf_token = extract_csrf(login_page.text)
    client.post(
        "/login",
        data={"username": "admin", "password": "ChangeMe123!", "csrf_token": csrf_token},
        follow_redirects=True,
    )


def test_health_endpoint() -> None:
    with build_test_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_login_and_dashboard_access() -> None:
    with build_test_client() as client:
        login_page = client.get("/login")
        csrf_token = extract_csrf(login_page.text)
        response = client.post(
            "/login",
            data={"username": "admin", "password": "ChangeMe123!", "csrf_token": csrf_token},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "AthletiSync District" in response.text
        assert "Configured Mappings" in response.text
        assert "Next scheduled sync at" in response.text


def test_dashboard_requires_authentication() -> None:
    with build_test_client() as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_settings_update_creates_school_year() -> None:
    with build_test_client() as client:
        login(client)

        settings_page = client.get("/settings")
        settings_csrf = extract_csrf(settings_page.text)
        response = client.post(
            "/settings",
            data={
                "district_name": "Central District",
                "server_base_url": "http://172.16.1.77",
                "timezone": "America/Chicago",
                "polling_interval_minutes": 30,
                "event_title_template": "{school} {sport} {level} vs {opponent}",
                "event_description_template": "School: {school}\\nSport: {sport}\\nOpponent: {opponent}",
                "cancellation_behavior": "mark_cancelled",
                "sync_retry_count": 2,
                "log_retention_days": 30,
                "csrf_token": settings_csrf,
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "Automatic school-year handling" in response.text or "School Year Handling" in response.text
        assert 'value="http://172.16.1.77"' in response.text


def test_import_sport_from_school_flow() -> None:
    with build_test_client() as client:
        login(client)

        schools_page = client.get("/schools")
        schools_csrf = extract_csrf(schools_page.text)
        response = client.post(
            "/schools/1/activities/import",
            data={"csrf_token": schools_csrf, "activity_name": "Football"},
        )

        assert response.status_code == 200
        catalog_page = client.get("/catalog")
        assert "Football" in catalog_page.text


def test_mappings_page_shows_source_activity_fields() -> None:
    with build_test_client() as client:
        login(client)

        response = client.get("/mappings")
        assert response.status_code == 200
        assert "MSHSAA Activity ID" in response.text


def test_settings_page_shows_formatter_controls() -> None:
    with build_test_client() as client:
        login(client)

        response = client.get("/settings")
        assert response.status_code == 200
        assert "Event Title Template" in response.text


def test_catalog_page_shows_sport_formatter_overrides() -> None:
    with build_test_client() as client:
        login(client)

        catalog_page = client.get("/catalog")
        catalog_csrf = extract_csrf(catalog_page.text)
        response = client.post(
            "/catalog/sports",
            data={"name": "Golf", "slug": "golf", "csrf_token": catalog_csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Formatter Overrides" in response.text
        assert "Title Override" in response.text


def test_can_save_sport_formatter_override() -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Sport

    with build_test_client() as client:
        login(client)

        catalog_page = client.get("/catalog")
        catalog_csrf = extract_csrf(catalog_page.text)
        client.post(
            "/catalog/sports",
            data={"name": "Golf", "slug": "golf", "csrf_token": catalog_csrf},
            follow_redirects=True,
        )

        db = SessionLocal()
        try:
            sport_id = db.scalar(select(Sport.id).where(Sport.name == "Golf"))
        finally:
            db.close()

        updated_catalog_page = client.get("/catalog")
        updated_catalog_csrf = extract_csrf(updated_catalog_page.text)
        response = client.post(
            f"/catalog/sports/{sport_id}/formatter",
            data={
                "event_title_template_override": "{school} {sport} at {location} - {participants}",
                "event_description_template_override": "Participants: {participants}",
                "csrf_token": updated_catalog_csrf,
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "{school} {sport} at {location} - {participants}" in response.text


def test_school_source_review_page_loads() -> None:
    with build_test_client() as client:
        login(client)

        response = client.get("/schools/1/source")
        assert response.status_code == 200


def test_source_review_page_shows_mapping_actions() -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import GoogleCalendar, School, SchoolYear, SyncMapping

    with build_test_client() as client:
        login(client)

        db = SessionLocal()
        try:
            db.add(School(name="Brookfield R-III School District", mshsaa_url="https://www.mshsaa.org/MySchool/?s=244"))
            db.flush()
            automatic_year = db.scalar(select(SchoolYear).where(SchoolYear.label == "Automatic (Current and Future)"))
            calendar = GoogleCalendar(display_name="Athletics", calendar_id="athletics@example.com")
            db.add(calendar)
            db.flush()
            db.add(
                SyncMapping(
                    school_year_id=automatic_year.id,
                    school_id=1,
                    google_calendar_id=calendar.id,
                    source_activity_id="19",
                    source_activity_name="High School Football",
                    enabled=True,
                )
            )
            db.commit()
        finally:
            db.close()

        response = client.get("/schools/1/source")
        assert response.status_code == 200
        assert "Edit" in response.text
        assert "Delete" in response.text


def test_schedule_preview_allows_mapping_when_activity_has_no_schedulable_rows(monkeypatch) -> None:
    from app.db.session import SessionLocal
    from app.models import School
    from app.routes import schools as schools_routes

    async def fake_fetch_activity_schedule(self, school_url, activity_id, year_value=None):
        return {
            "rows": [],
            "schedule_url": "https://www.mshsaa.org/MySchool/Schedule.aspx?s=244&alg=19",
            "school_year": "2026-2027",
        }

    monkeypatch.setattr(schools_routes.MSHSAAClient, "fetch_activity_schedule", fake_fetch_activity_schedule)

    with build_test_client() as client:
        login(client)

        db = SessionLocal()
        try:
            school = School(name="Brookfield R-III High School", mshsaa_url="https://www.mshsaa.org/MySchool/?s=244")
            db.add(school)
            db.commit()
            db.refresh(school)
            school_id = school.id
        finally:
            db.close()

        source_page = client.get(f"/schools/{school_id}/source")
        csrf_token = extract_csrf(source_page.text)
        response = client.post(
            f"/schools/{school_id}/activities/19/schedule",
            data={"csrf_token": csrf_token, "activity_name": "High School Football"},
        )

        assert response.status_code == 200
        assert "You can still pair it to a Google Calendar now" in response.text
        assert "No events are posted for this activity yet." in response.text
        assert "Save Mapping" in response.text


def test_save_mapping_allows_google_calendar_when_activity_has_no_schedulable_rows(monkeypatch) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import GoogleCalendar, School, SchoolYear, SyncMapping

    with build_test_client() as client:
        login(client)

        db = SessionLocal()
        try:
            automatic_year = db.scalar(select(SchoolYear).where(SchoolYear.label == "Automatic (Current and Future)"))
            school = School(name="Brookfield R-III High School", mshsaa_url="https://www.mshsaa.org/MySchool/?s=244")
            db.add(school)
            calendar = GoogleCalendar(display_name="Athletics", calendar_id="athletics@example.com")
            db.add(calendar)
            db.commit()
            db.refresh(school)
            db.refresh(calendar)
            school_id = school.id
        finally:
            db.close()

        mappings_page = client.get("/mappings")
        csrf_token = extract_csrf(mappings_page.text)
        response = client.post(
            "/mappings",
            data={
                "school_year_id": automatic_year.id,
                "school_id": school_id,
                "sport_name": "High School Football",
                "google_calendar_id": calendar.id,
                "source_activity_id": "19",
                "source_activity_name": "High School Football",
                "enabled": "on",
                "sync_behavior": "standard",
                "notes": "",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )

        assert response.status_code == 200

        db = SessionLocal()
        try:
            mapping = db.query(SyncMapping).one()
            assert mapping.google_calendar_id == calendar.id
        finally:
            db.close()


def test_google_page_shows_oauth_guidance() -> None:
    with build_test_client() as client:
        login(client)
        response = client.get("/google")
        assert response.status_code == 200
        assert "Google OAuth Configuration" in response.text
        assert "Add Google Account Connection" in response.text
        assert "Sign In With Google" in response.text
        assert "Save Calendar Destination" in response.text
        assert "Current redirect URI" in response.text
        assert "Create Credentials" in response.text
        assert "OAuth client ID" in response.text
        assert "Authorized JavaScript Origin" in response.text
        assert "Authorized Redirect URI" in response.text


def test_can_remove_google_calendar_destination() -> None:
    from app.db.session import SessionLocal
    from app.models import GoogleCalendar

    with build_test_client() as client:
        login(client)
        db = SessionLocal()
        try:
            calendar = GoogleCalendar(display_name="Test Calendar", calendar_id="test-calendar@example.com")
            db.add(calendar)
            db.commit()
            db.refresh(calendar)
            calendar_id = calendar.id
        finally:
            db.close()

        google_page = client.get("/google")
        csrf_token = extract_csrf(google_page.text)
        response = client.post(
            f"/google/calendars/{calendar_id}/delete",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "Removed calendar destination: Test Calendar." in response.text

        db = SessionLocal()
        try:
            assert db.get(GoogleCalendar, calendar_id) is None
        finally:
            db.close()


def test_can_remove_google_auth_profile_when_unused() -> None:
    from app.db.session import SessionLocal
    from app.models import GoogleAuthProfile

    with build_test_client() as client:
        login(client)
        db = SessionLocal()
        try:
            profile = GoogleAuthProfile(name="Test Profile", auth_type="oauth")
            db.add(profile)
            db.commit()
            db.refresh(profile)
            profile_id = profile.id
        finally:
            db.close()

        google_page = client.get("/google")
        csrf_token = extract_csrf(google_page.text)
        response = client.post(
            f"/google/profiles/{profile_id}/delete",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "Removed auth profile: Test Profile." in response.text

        db = SessionLocal()
        try:
            assert db.get(GoogleAuthProfile, profile_id) is None
        finally:
            db.close()


def test_cannot_remove_google_auth_profile_while_calendars_still_use_it() -> None:
    from app.db.session import SessionLocal
    from app.models import GoogleAuthProfile, GoogleCalendar

    with build_test_client() as client:
        login(client)
        db = SessionLocal()
        try:
            profile = GoogleAuthProfile(name="In Use Profile", auth_type="oauth")
            db.add(profile)
            db.commit()
            db.refresh(profile)
            db.add(
                GoogleCalendar(
                    display_name="Used Calendar",
                    calendar_id="used-calendar@example.com",
                    auth_profile_id=profile.id,
                )
            )
            db.commit()
            profile_id = profile.id
        finally:
            db.close()

        google_page = client.get("/google")
        csrf_token = extract_csrf(google_page.text)
        response = client.post(
            f"/google/profiles/{profile_id}/delete",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "This auth profile is still assigned to one or more calendar destinations." in response.text


def test_google_page_uses_server_base_url_for_redirect_hint() -> None:
    with build_test_client() as client:
        login(client)
        settings_page = client.get("/settings")
        settings_csrf = extract_csrf(settings_page.text)
        client.post(
            "/settings",
            data={
                "district_name": "AthletiSync District",
                "server_base_url": "http://172.16.1.77",
                "timezone": "America/Chicago",
                "polling_interval_minutes": 30,
                "event_title_template": "{school} {sport} {level} vs {opponent}",
                "event_description_template": "School: {school}",
                "cancellation_behavior": "mark_cancelled",
                "sync_retry_count": 2,
                "log_retention_days": 30,
                "csrf_token": settings_csrf,
            },
            follow_redirects=True,
        )
        response = client.get("/google")
        assert response.status_code == 200
        assert "http://172.16.1.77" in response.text
        assert "http://172.16.1.77/google/oauth/callback" in response.text


def test_server_base_url_without_scheme_is_normalized_for_google_values() -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AppSetting

    with build_test_client() as client:
        login(client)
        settings_page = client.get("/settings")
        settings_csrf = extract_csrf(settings_page.text)
        client.post(
            "/settings",
            data={
                "district_name": "AthletiSync District",
                "server_base_url": "athletisync.brookfieldr3.org",
                "timezone": "America/Chicago",
                "polling_interval_minutes": 30,
                "event_title_template": "{school} {sport} {level} vs {opponent}",
                "event_description_template": "School: {school}",
                "cancellation_behavior": "mark_cancelled",
                "sync_retry_count": 2,
                "log_retention_days": 30,
                "csrf_token": settings_csrf,
            },
            follow_redirects=True,
        )

        db = SessionLocal()
        try:
            settings = db.scalar(select(AppSetting))
            assert settings is not None
            assert settings.server_base_url == "https://athletisync.brookfieldr3.org"
        finally:
            db.close()

        response = client.get("/google")
        assert response.status_code == 200
        assert "https://athletisync.brookfieldr3.org" in response.text
        assert "https://athletisync.brookfieldr3.org/google/oauth/callback" in response.text


def test_can_save_google_oauth_settings_on_google_page() -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AppSetting

    with build_test_client() as client:
        login(client)
        google_page = client.get("/google")
        settings_csrf = extract_csrf(google_page.text)
        response = client.post(
            "/google/oauth/config",
            data={
                "google_oauth_client_id": "ui-client-id",
                "google_oauth_redirect_uri": "http://testserver/google/oauth/callback",
                "csrf_token": settings_csrf,
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Saved Google OAuth configuration." in response.text

        db = SessionLocal()
        try:
            settings = db.scalar(select(AppSetting))
            assert settings is not None
            assert settings.google_oauth_client_id == "ui-client-id"
            assert settings.google_oauth_redirect_uri == "http://testserver/google/oauth/callback"
        finally:
            db.close()


def test_google_page_does_not_round_trip_client_secret_from_ui() -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AppSetting

    db = SessionLocal()
    try:
        settings = db.scalar(select(AppSetting))
        if settings is None:
            settings = AppSetting()
            db.add(settings)
        settings.google_oauth_client_secret = "legacy-db-secret"
        db.commit()
    finally:
        db.close()

    with build_test_client() as client:
        login(client)
        response = client.get("/google")
        assert response.status_code == 200
        assert 'name="google_oauth_client_secret"' not in response.text
        assert "GOOGLE_OAUTH_CLIENT_SECRET" in response.text


def test_calendar_access_test_requires_auth_profile() -> None:
    from app.db.session import SessionLocal
    from app.models import GoogleCalendar

    with build_test_client() as client:
        login(client)
        db = SessionLocal()
        try:
            calendar = GoogleCalendar(display_name="No Auth", calendar_id="calendar@example.com")
            db.add(calendar)
            db.commit()
            db.refresh(calendar)
        finally:
            db.close()

        google_page = client.get("/google")
        csrf_token = extract_csrf(google_page.text)
        response = client.post(
            f"/google/calendars/{calendar.id}/test",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        assert "missing an auth profile" in response.text


def test_google_oauth_start_and_callback_preserve_code_verifier(monkeypatch) -> None:
    from app.routes import google as google_routes

    captured: dict[str, str | None] = {}

    class FakeCredentials:
        token = "access-token"
        refresh_token = "refresh-token"
        scopes = [
            "https://www.googleapis.com/auth/calendar",
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
        ]

    class FakeFlow:
        def __init__(self, *, state=None, redirect_uri=None, code_verifier=None):
            self.state = state
            self.redirect_uri = redirect_uri
            self.code_verifier = code_verifier or "verifier-123"
            self.credentials = FakeCredentials()

        @classmethod
        def from_client_config(cls, _client_config, scopes=None, state=None, redirect_uri=None, code_verifier=None):
            captured["callback_code_verifier"] = code_verifier
            return cls(state=state, redirect_uri=redirect_uri, code_verifier=code_verifier)

        def authorization_url(self, **_kwargs):
            return (f"https://accounts.google.com/o/oauth2/auth?state={self.state}", self.state)

        def fetch_token(self, authorization_response):
            captured["authorization_response"] = authorization_response

    class FakeResponse:
        is_success = True

        @staticmethod
        def json():
            return {"email": "calendar-admin@example.org"}

    monkeypatch.setattr(google_routes, "Flow", FakeFlow)
    monkeypatch.setattr(google_routes.httpx, "get", lambda *args, **kwargs: FakeResponse())

    with build_test_client() as client:
        login(client)

        settings_page = client.get("/settings")
        settings_csrf = extract_csrf(settings_page.text)
        client.post(
            "/settings",
            data={
                "district_name": "AthletiSync District",
                "server_base_url": "https://athletisync.brookfieldr3.org",
                "timezone": "America/Chicago",
                "polling_interval_minutes": 30,
                "event_title_template": "{school} {sport} {level} vs {opponent}",
                "event_description_template": "School: {school}",
                "cancellation_behavior": "mark_cancelled",
                "sync_retry_count": 2,
                "log_retention_days": 30,
                "csrf_token": settings_csrf,
            },
            follow_redirects=True,
        )

        google_page = client.get("/google")
        csrf_token = extract_csrf(google_page.text)
        start_response = client.post(
            "/google/oauth/start",
            data={"name": "District Calendar Manager", "csrf_token": csrf_token},
            follow_redirects=False,
        )
        assert start_response.status_code == 303
        callback_state = parse_qs(urlsplit(start_response.headers["location"]).query)["state"][0]

        callback_response = client.get(
            f"/google/oauth/callback?state={callback_state}&code=test-code",
            follow_redirects=True,
        )
        assert callback_response.status_code == 200
        assert captured["callback_code_verifier"] == "verifier-123"
        assert "District Calendar Manager" in callback_response.text
        assert "calendar-admin@example.org" in callback_response.text
