from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_user
from app.models import GoogleAuthProfile, GoogleCalendar
from app.security import ensure_csrf_token, verify_csrf
from app.services.google_calendar import DryRunCalendarGateway, GoogleCalendarGateway

router = APIRouter(prefix="/google", tags=["google"])


@router.get("", response_class=HTMLResponse)
def google_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    context = {
        "request": request,
        "profiles": db.scalars(select(GoogleAuthProfile).order_by(GoogleAuthProfile.name)).all(),
        "calendars": db.scalars(select(GoogleCalendar).order_by(GoogleCalendar.display_name)).all(),
        "csrf_token": ensure_csrf_token(request),
    }
    return request.app.state.templates.TemplateResponse("google/index.html", context)


@router.post("/profiles")
def create_profile(
    request: Request,
    name: str = Form(...),
    service_account_json: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    db.add(GoogleAuthProfile(name=name.strip(), service_account_json=service_account_json.strip()))
    db.commit()
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
    return RedirectResponse("/google", status_code=303)


@router.post("/profiles/{profile_id}/test", response_class=HTMLResponse)
def test_profile(profile_id: int, request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    verify_csrf(request, request.headers.get("X-CSRF-Token"))
    profile = db.get(GoogleAuthProfile, profile_id)
    try:
        gateway = GoogleCalendarGateway(profile) if profile else DryRunCalendarGateway()
        ok, message = gateway.test_connection()
    except Exception as exc:  # pragma: no cover - UI fallback path
        ok, message = False, str(exc)
    return request.app.state.templates.TemplateResponse(
        "partials/banner.html",
        {"request": request, "kind": "success" if ok else "error", "message": message},
    )
