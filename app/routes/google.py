import secrets

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.dependencies import require_user
from app.models import AppSetting, GoogleAuthProfile, GoogleCalendar
from app.security import decrypt_secret, encrypt_secret, ensure_csrf_token, verify_csrf
from app.services.google_calendar import DryRunCalendarGateway, GoogleCalendarGateway
from app.services.url_helpers import google_oauth_origin, google_oauth_redirect_uri_from_base_url

try:
    from google_auth_oauthlib.flow import Flow
except ImportError:  # pragma: no cover - optional dependency
    Flow = None

router = APIRouter(prefix="/google", tags=["google"])
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
GOOGLE_USERINFO_EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"


def pop_google_banner(request: Request) -> dict | None:
    return request.session.pop("google_banner", None)


def set_google_banner(request: Request, kind: str, message: str) -> None:
    request.session["google_banner"] = {"kind": kind, "message": message}


def google_oauth_redirect_uri(request: Request) -> str:
    app_settings = request.state.google_app_settings if hasattr(request.state, "google_app_settings") else None
    settings = request.app.state.settings
    if app_settings and app_settings.server_base_url:
        return google_oauth_redirect_uri_from_base_url(app_settings.server_base_url) or str(
            request.url_for("google_oauth_callback")
        )
    return (
        (app_settings.google_oauth_redirect_uri if app_settings else None)
        or settings.google_oauth_redirect_uri
        or str(request.url_for("google_oauth_callback"))
    )


def get_google_app_settings(db: Session) -> AppSetting:
    return db.scalar(select(AppSetting)) or AppSetting()


def google_oauth_ready(app_settings: AppSetting, request: Request) -> bool:
    settings = request.app.state.settings
    client_id = app_settings.google_oauth_client_id or settings.google_oauth_client_id
    client_secret = settings.google_oauth_client_secret or decrypt_secret(
        app_settings.google_oauth_client_secret,
        settings.app_secret_key,
    )
    return bool(client_id and client_secret)


@router.get("", response_class=HTMLResponse)
def google_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    app_settings = get_google_app_settings(db)
    request.state.google_app_settings = app_settings
    context = {
        "request": request,
        "profiles": db.scalars(
            select(GoogleAuthProfile).where(GoogleAuthProfile.auth_type == "oauth").order_by(GoogleAuthProfile.name)
        ).all(),
        "calendars": db.scalars(
            select(GoogleCalendar).options(selectinload(GoogleCalendar.auth_profile)).order_by(GoogleCalendar.display_name)
        ).all(),
        "csrf_token": ensure_csrf_token(request),
        "google_banner": pop_google_banner(request),
        "google_oauth_ready": google_oauth_ready(app_settings, request),
        "google_oauth_origin": google_oauth_origin(app_settings.server_base_url),
        "google_oauth_redirect_uri": google_oauth_redirect_uri(request),
        "google_settings": app_settings,
        "google_ui_secret_configured": bool(app_settings.google_oauth_client_secret),
    }
    return request.app.state.templates.TemplateResponse(request, "google/index.html", context)


@router.post("/oauth/config")
def save_google_oauth_config(
    request: Request,
    google_oauth_client_id: str = Form(default=""),
    google_oauth_client_secret: str = Form(default=""),
    google_oauth_redirect_uri: str = Form(default=""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    settings = db.scalar(select(AppSetting))
    if settings is None:
        settings = AppSetting()
        db.add(settings)
    settings.google_oauth_client_id = (google_oauth_client_id or "").strip() or None
    submitted_secret = (google_oauth_client_secret or "").strip()
    if submitted_secret:
        settings.google_oauth_client_secret = encrypt_secret(submitted_secret, request.app.state.settings.app_secret_key)
    settings.google_oauth_redirect_uri = (google_oauth_redirect_uri or "").strip() or None
    db.commit()
    set_google_banner(request, "success", "Saved Google OAuth configuration.")
    return RedirectResponse("/google", status_code=303)


@router.post("/oauth/start")
def start_google_oauth(
    request: Request,
    name: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    app_settings = get_google_app_settings(db)
    request.state.google_app_settings = app_settings
    settings = request.app.state.settings
    if Flow is None:
        set_google_banner(request, "error", "Install AthletiSync with the google extra to enable Google OAuth.")
        return RedirectResponse("/google", status_code=303)
    client_id = app_settings.google_oauth_client_id or settings.google_oauth_client_id
    client_secret = settings.google_oauth_client_secret or decrypt_secret(
        app_settings.google_oauth_client_secret,
        settings.app_secret_key,
    )
    if not client_id or not client_secret:
        set_google_banner(
            request,
            "error",
            "Missing Google OAuth client settings. Fill in the Google OAuth Configuration section on this page first.",
        )
        return RedirectResponse("/google", status_code=303)

    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_profile_name"] = name.strip()
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[GOOGLE_CALENDAR_SCOPE, "openid", GOOGLE_USERINFO_EMAIL_SCOPE],
        state=state,
        redirect_uri=google_oauth_redirect_uri(request),
    )
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    request.session["google_oauth_code_verifier"] = getattr(flow, "code_verifier", None)
    return RedirectResponse(authorization_url, status_code=303)


@router.get("/oauth/callback", name="google_oauth_callback")
def google_oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    expected_state = request.session.pop("google_oauth_state", None)
    profile_name = request.session.pop("google_oauth_profile_name", None)
    code_verifier = request.session.pop("google_oauth_code_verifier", None)
    state = request.query_params.get("state")
    if not expected_state or not state or not secrets.compare_digest(expected_state, state):
        set_google_banner(request, "error", "Google OAuth state validation failed. Please try again.")
        return RedirectResponse("/google", status_code=303)
    if not profile_name:
        set_google_banner(request, "error", "Missing pending Google OAuth profile name. Please try again.")
        return RedirectResponse("/google", status_code=303)
    if db.scalar(select(GoogleAuthProfile).where(GoogleAuthProfile.name == profile_name)):
        set_google_banner(request, "error", f"A Google auth profile named '{profile_name}' already exists.")
        return RedirectResponse("/google", status_code=303)

    app_settings = get_google_app_settings(db)
    request.state.google_app_settings = app_settings
    settings = request.app.state.settings
    if Flow is None:
        set_google_banner(request, "error", "Install AthletiSync with the google extra to enable Google OAuth.")
        return RedirectResponse("/google", status_code=303)
    client_id = app_settings.google_oauth_client_id or settings.google_oauth_client_id
    client_secret = settings.google_oauth_client_secret or decrypt_secret(
        app_settings.google_oauth_client_secret,
        settings.app_secret_key,
    )
    if not client_id or not client_secret:
        set_google_banner(request, "error", "Missing Google OAuth client settings. Fill them in on the Google page.")
        return RedirectResponse("/google", status_code=303)

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[GOOGLE_CALENDAR_SCOPE, "openid", GOOGLE_USERINFO_EMAIL_SCOPE],
        state=state,
        redirect_uri=google_oauth_redirect_uri(request),
        code_verifier=code_verifier,
    )
    try:
        flow.fetch_token(authorization_response=str(request.url))
    except Exception as exc:  # pragma: no cover - network callback path
        set_google_banner(request, "error", f"Google OAuth token exchange failed: {exc}")
        return RedirectResponse("/google", status_code=303)

    credentials = flow.credentials
    account_email = None
    if credentials.token:
        try:
            response = httpx.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {credentials.token}"},
                timeout=10.0,
            )
            if response.is_success:
                account_email = response.json().get("email")
        except httpx.HTTPError:
            account_email = None
    db.add(
        GoogleAuthProfile(
            name=profile_name,
            auth_type="oauth",
            oauth_account_email=account_email,
            oauth_refresh_token=credentials.refresh_token,
            oauth_scopes=" ".join(credentials.scopes or [GOOGLE_CALENDAR_SCOPE]),
        )
    )
    db.commit()
    set_google_banner(request, "success", f"Saved OAuth profile: {profile_name}. Now add a calendar below.")
    return RedirectResponse("/google", status_code=303)


@router.post("/calendars")
def create_calendar(
    request: Request,
    display_name: str = Form(...),
    calendar_id: str = Form(...),
    auth_profile_id: int | None = Form(default=None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    db.add(
        GoogleCalendar(
            display_name=display_name.strip(),
            calendar_id=calendar_id.strip(),
            auth_profile_id=auth_profile_id,
        )
    )
    db.commit()
    set_google_banner(request, "success", f"Saved calendar destination: {display_name.strip()}.")
    return RedirectResponse("/google", status_code=303)


@router.post("/calendars/{calendar_id}/delete")
def delete_calendar(
    calendar_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    calendar = db.get(GoogleCalendar, calendar_id)
    if not calendar:
        set_google_banner(request, "error", "Calendar destination not found.")
        return RedirectResponse("/google", status_code=303)
    if calendar.mappings:
        set_google_banner(
            request,
            "error",
            "This calendar destination is still assigned to one or more mappings. Remove those assignments first.",
        )
        return RedirectResponse("/google", status_code=303)
    display_name = calendar.display_name
    db.delete(calendar)
    db.commit()
    set_google_banner(request, "success", f"Removed calendar destination: {display_name}.")
    return RedirectResponse("/google", status_code=303)


@router.post("/profiles/{profile_id}/delete")
def delete_profile(
    profile_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    profile = db.get(GoogleAuthProfile, profile_id)
    if not profile:
        set_google_banner(request, "error", "Google auth profile not found.")
        return RedirectResponse("/google", status_code=303)
    if profile.calendars:
        set_google_banner(
            request,
            "error",
            "This auth profile is still assigned to one or more calendar destinations. Remove those calendars first.",
        )
        return RedirectResponse("/google", status_code=303)
    profile_name = profile.name
    db.delete(profile)
    db.commit()
    set_google_banner(request, "success", f"Removed auth profile: {profile_name}.")
    return RedirectResponse("/google", status_code=303)


@router.post("/profiles/{profile_id}/test", response_class=HTMLResponse)
def test_profile(profile_id: int, request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    verify_csrf(request, request.headers.get("X-CSRF-Token"))
    profile = db.get(GoogleAuthProfile, profile_id)
    try:
        app_settings = get_google_app_settings(db)
        gateway = GoogleCalendarGateway(profile, app_settings=app_settings) if profile else DryRunCalendarGateway()
        ok, message = gateway.test_connection()
    except Exception as exc:  # pragma: no cover - UI fallback path
        ok, message = False, str(exc)
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/banner.html",
        {"request": request, "kind": "success" if ok else "error", "message": message},
    )


@router.post("/calendars/{calendar_id}/test", response_class=HTMLResponse)
def test_calendar(calendar_id: int, request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    verify_csrf(request, request.headers.get("X-CSRF-Token"))
    calendar = db.get(GoogleCalendar, calendar_id)
    if not calendar or not calendar.auth_profile_id:
        ok, message = False, "This calendar is missing an auth profile."
    else:
        profile = db.get(GoogleAuthProfile, calendar.auth_profile_id)
        try:
            app_settings = get_google_app_settings(db)
            gateway = GoogleCalendarGateway(profile, app_settings=app_settings) if profile else DryRunCalendarGateway()
            ok, message = gateway.test_calendar_access(calendar.calendar_id)
        except Exception as exc:  # pragma: no cover - UI fallback path
            ok, message = False, str(exc)
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/banner.html",
        {"request": request, "kind": "success" if ok else "error", "message": message},
    )
