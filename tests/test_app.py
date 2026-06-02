from __future__ import annotations

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
                "google_oauth_client_secret": "ui-client-secret",
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
            assert settings.google_oauth_client_secret == "ui-client-secret"
            assert settings.google_oauth_redirect_uri == "http://testserver/google/oauth/callback"
        finally:
            db.close()


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
