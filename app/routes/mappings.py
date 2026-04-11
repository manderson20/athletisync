from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_user
from app.models import GoogleCalendar, School, SchoolYear, Sport, SportLevel, SyncMapping
from app.schemas import MappingFormData
from app.security import ensure_csrf_token, verify_csrf
from app.services.mappings import upsert_mapping

router = APIRouter(prefix="/mappings", tags=["mappings"])


@router.get("", response_class=HTMLResponse)
def mappings_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    context = {
        "request": request,
        "school_years": db.scalars(select(SchoolYear).order_by(SchoolYear.label.desc())).all(),
        "schools": db.scalars(select(School).order_by(School.name)).all(),
        "sports": db.scalars(select(Sport).order_by(Sport.name)).all(),
        "levels": db.scalars(select(SportLevel).order_by(SportLevel.name)).all(),
        "calendars": db.scalars(select(GoogleCalendar).order_by(GoogleCalendar.display_name)).all(),
        "mappings": db.scalars(select(SyncMapping).order_by(SyncMapping.id.desc())).all(),
        "csrf_token": ensure_csrf_token(request),
    }
    return request.app.state.templates.TemplateResponse("mappings/index.html", context)


@router.post("")
def save_mapping(
    request: Request,
    school_year_id: int = Form(...),
    school_id: int = Form(...),
    sport_id: int | None = Form(default=None),
    level_id: int | None = Form(default=None),
    google_calendar_id: int | None = Form(default=None),
    enabled: str | None = Form(default=None),
    sync_behavior: str = Form(default="standard"),
    notes: str | None = Form(default=None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    payload = MappingFormData(
        school_year_id=school_year_id,
        school_id=school_id,
        sport_id=sport_id,
        level_id=level_id,
        google_calendar_id=google_calendar_id,
        enabled=enabled == "on",
        sync_behavior=sync_behavior,
        notes=notes,
    )
    upsert_mapping(db, payload)
    return RedirectResponse("/mappings", status_code=303)
