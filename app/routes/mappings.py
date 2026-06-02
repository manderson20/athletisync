from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.dependencies import require_user
from app.models import GoogleCalendar, School, SchoolYear, Sport, SportLevel, SyncMapping
from app.schemas import MappingFormData
from app.security import ensure_csrf_token, verify_csrf
from app.services.catalog import ensure_level, ensure_sport
from app.services.mappings import upsert_mapping
from app.services.school_years import (
    AUTOMATIC_SCHOOL_YEAR_LABEL,
    current_school_year_label,
    ensure_automatic_school_year,
    ensure_school_year,
)

router = APIRouter(prefix="/mappings", tags=["mappings"])


def pop_mapping_banner(request: Request) -> dict | None:
    return request.session.pop("mapping_banner", None)


def set_mapping_banner(request: Request, kind: str, message: str) -> None:
    request.session["mapping_banner"] = {"kind": kind, "message": message}


@router.get("", response_class=HTMLResponse)
def mappings_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    automatic_school_year = ensure_automatic_school_year(db)
    current_school_year = ensure_school_year(db, current_school_year_label())
    prefill = {
        "school_id": request.query_params.get("school_id", ""),
        "source_activity_id": request.query_params.get("source_activity_id", ""),
        "source_activity_name": request.query_params.get("source_activity_name", ""),
    }
    context = {
        "request": request,
        "school_years": [automatic_school_year, current_school_year]
        + db.scalars(
            select(SchoolYear)
            .where(SchoolYear.label.not_in([AUTOMATIC_SCHOOL_YEAR_LABEL, current_school_year.label]))
            .order_by(SchoolYear.label.desc())
        ).all(),
        "schools": db.scalars(select(School).order_by(School.name)).all(),
        "sports": db.scalars(select(Sport).order_by(Sport.name)).all(),
        "levels": db.scalars(select(SportLevel).order_by(SportLevel.name)).all(),
        "calendars": db.scalars(select(GoogleCalendar).order_by(GoogleCalendar.display_name)).all(),
        "mappings": db.scalars(
            select(SyncMapping)
            .options(
                joinedload(SyncMapping.school_year),
                joinedload(SyncMapping.school),
                joinedload(SyncMapping.sport),
                joinedload(SyncMapping.level),
                joinedload(SyncMapping.google_calendar),
            )
            .order_by(SyncMapping.id.desc())
        ).all(),
        "automatic_school_year_label": AUTOMATIC_SCHOOL_YEAR_LABEL,
        "current_school_year_label": current_school_year.label,
        "prefill": prefill,
        "mapping_banner": pop_mapping_banner(request),
        "csrf_token": ensure_csrf_token(request),
    }
    return request.app.state.templates.TemplateResponse(request, "mappings/index.html", context)


@router.post("")
def save_mapping(
    request: Request,
    school_year_id: int = Form(...),
    school_id: int = Form(...),
    sport_id: int | None = Form(default=None),
    level_id: int | None = Form(default=None),
    sport_name: str | None = Form(default=None),
    level_name: str | None = Form(default=None),
    google_calendar_id: int | None = Form(default=None),
    source_activity_id: str | None = Form(default=None),
    source_activity_name: str | None = Form(default=None),
    enabled: str | None = Form(default=None),
    sync_behavior: str = Form(default="standard"),
    notes: str | None = Form(default=None),
    return_to: str | None = Form(default=None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    if sport_id is None and sport_name and sport_name.strip():
        sport, _ = ensure_sport(db, sport_name.strip())
        sport_id = sport.id
    if level_id is None and level_name and level_name.strip():
        level, _ = ensure_level(db, level_name.strip())
        level_id = level.id
    payload = MappingFormData(
        school_year_id=school_year_id,
        school_id=school_id,
        sport_id=sport_id,
        level_id=level_id,
        google_calendar_id=google_calendar_id,
        source_activity_id=source_activity_id or None,
        source_activity_name=source_activity_name or None,
        enabled=enabled == "on",
        sync_behavior=sync_behavior,
        notes=notes,
    )
    upsert_mapping(db, payload)
    return RedirectResponse(return_to or "/mappings", status_code=303)


@router.post("/{mapping_id}")
def update_mapping(
    mapping_id: int,
    request: Request,
    google_calendar_id: int | None = Form(default=None),
    enabled: str | None = Form(default=None),
    sync_behavior: str = Form(default="standard"),
    notes: str | None = Form(default=None),
    return_to: str | None = Form(default=None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    mapping = db.get(SyncMapping, mapping_id)
    if mapping:
        mapping.google_calendar_id = google_calendar_id
        mapping.sync_behavior = sync_behavior
        mapping.notes = notes
        mapping.enabled = enabled == "on"
        db.add(mapping)
        db.commit()
    return RedirectResponse(return_to or "/mappings", status_code=303)


@router.post("/{mapping_id}/delete")
def delete_mapping(
    mapping_id: int,
    request: Request,
    return_to: str | None = Form(default=None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    mapping = db.get(SyncMapping, mapping_id)
    if mapping:
        db.delete(mapping)
        db.commit()
    return RedirectResponse(return_to or "/mappings", status_code=303)
