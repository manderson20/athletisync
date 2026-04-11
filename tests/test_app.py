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
        login_page = client.get("/login")
        csrf_token = extract_csrf(login_page.text)
        client.post(
            "/login",
            data={"username": "admin", "password": "ChangeMe123!", "csrf_token": csrf_token},
            follow_redirects=True,
        )

        settings_page = client.get("/settings")
        settings_csrf = extract_csrf(settings_page.text)
        response = client.post(
            "/settings",
            data={
                "district_name": "Central District",
                "timezone": "America/Chicago",
                "polling_interval_minutes": 30,
                "default_school_year_label": "2026-2027",
                "cancellation_behavior": "mark_cancelled",
                "sync_retry_count": 2,
                "log_retention_days": 30,
                "csrf_token": settings_csrf,
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        school_years_page = client.get("/school-years")
        assert "2026-2027" in school_years_page.text


def test_import_sport_from_school_flow() -> None:
    with build_test_client() as client:
        login_page = client.get("/login")
        csrf_token = extract_csrf(login_page.text)
        client.post(
            "/login",
            data={"username": "admin", "password": "ChangeMe123!", "csrf_token": csrf_token},
            follow_redirects=True,
        )

        schools_page = client.get("/schools")
        schools_csrf = extract_csrf(schools_page.text)
        response = client.post(
            "/schools/1/activities/import",
            data={"csrf_token": schools_csrf, "activity_name": "Football"},
        )

        assert response.status_code == 200
        catalog_page = client.get("/catalog")
        assert "Football" in catalog_page.text


def test_school_source_review_page_loads() -> None:
    with build_test_client() as client:
        login_page = client.get("/login")
        csrf_token = extract_csrf(login_page.text)
        client.post(
            "/login",
            data={"username": "admin", "password": "ChangeMe123!", "csrf_token": csrf_token},
            follow_redirects=True,
        )

        response = client.get("/schools/1/source")
        assert response.status_code == 200
