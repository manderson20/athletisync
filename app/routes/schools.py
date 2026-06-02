from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app.config import get_settings
from app.db.session import get_db
from app.dependencies import require_user
from app.integrations.mshsaa import MSHSAAClient, row_has_schedulable_date
from app.models import GoogleCalendar, School, SyncMapping
from app.security import ensure_csrf_token, verify_csrf
from app.services.catalog import ensure_level, ensure_sport
from app.services.school_years import discover_and_ensure_school_years, ensure_automatic_school_year

router = APIRouter(prefix="/schools", tags=["schools"])


def pop_mapping_banner(request: Request) -> dict | None:
    return request.session.pop("mapping_banner", None)


@router.get("", response_class=HTMLResponse)
def schools_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    return request.app.state.templates.TemplateResponse(
        request,
        "schools/index.html",
        {
            "request": request,
            "schools": db.scalars(select(School).order_by(School.name)).all(),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.get("/{school_id}/source", response_class=HTMLResponse)
async def source_review_page(
    school_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    school = db.get(School, school_id)
    if not school:
        return RedirectResponse("/schools", status_code=303)

    activities: list[dict] = []
    school_year = None
    available_school_years: list[str] = []
    source_url = school.mshsaa_url
    school_year_options: list[dict[str, str]] = []
    kind = "success"
    message = "Review the discovered activities and choose one to inspect."
    automatic_school_year = ensure_automatic_school_year(db)
    calendars = db.scalars(select(GoogleCalendar).order_by(GoogleCalendar.display_name)).all()
    edit_mapping_id = request.query_params.get("edit_mapping_id")
    mappings = db.scalars(
        select(SyncMapping)
        .options(
            joinedload(SyncMapping.school_year),
            joinedload(SyncMapping.school),
            joinedload(SyncMapping.sport),
            joinedload(SyncMapping.level),
            joinedload(SyncMapping.google_calendar),
        )
        .where(SyncMapping.school_id == school_id)
        .order_by(SyncMapping.id.desc())
    ).all() if school else []
    edit_mapping = next((item for item in mappings if str(item.id) == edit_mapping_id), None)

    if not school.mshsaa_url:
        kind = "error"
        message = "Add an MSHSAA URL to this school before reviewing the source."
    else:
        client = MSHSAAClient(get_settings())
        try:
            result = await client.fetch_activity_catalog(school.mshsaa_url)
            activities = result["activities"]
            school_year = result["school_year"]
            available_school_years = result["available_school_years"]
            school_year_options = result["school_year_options"]
            source_url = result["source_url"]
            discover_and_ensure_school_years(db, available_school_years)
            message = f"Loaded {len(activities)} activities from the configured MSHSAA source."
        except Exception as exc:  # pragma: no cover - network-dependent UI path
            kind = "error"
            message = f"Could not load MSHSAA data: {exc}"

    return request.app.state.templates.TemplateResponse(
        request,
        "schools/source_review.html",
        {
            "request": request,
            "school": school,
            "activities": activities,
            "school_year": school_year,
            "available_school_years": available_school_years,
            "school_year_options": school_year_options,
            "source_url": source_url,
            "kind": kind,
            "message": message,
            "automatic_school_year": automatic_school_year,
            "calendars": calendars,
            "mappings": mappings,
            "edit_mapping": edit_mapping,
            "mapping_banner": pop_mapping_banner(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("")
def create_school(
    request: Request,
    name: str = Form(...),
    external_id: str | None = Form(default=None),
    mshsaa_url: str | None = Form(default=None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    db.add(School(name=name.strip(), external_id=external_id or None, mshsaa_url=mshsaa_url or None))
    db.commit()
    return RedirectResponse("/schools", status_code=303)


@router.post("/{school_id}/activities/{activity_id}/schedule", response_class=HTMLResponse)
async def preview_activity_schedule(
    school_id: int,
    activity_id: str,
    request: Request,
    csrf_token: str = Form(...),
    activity_name: str | None = Form(default=None),
    year_value: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    school = db.get(School, school_id)
    automatic_school_year = ensure_automatic_school_year(db)
    calendars = db.scalars(select(GoogleCalendar).order_by(GoogleCalendar.display_name)).all()
    if not school or not school.mshsaa_url:
        return request.app.state.templates.TemplateResponse(
            request,
            "partials/mshsaa_schedule.html",
            {
                "request": request,
                "kind": "error",
                "message": "Add an MSHSAA URL to the school before viewing schedules.",
                "rows": [],
                "school": school,
            "activity_name": None,
            "activity_id": activity_id,
            "schedule_url": None,
                "automatic_school_year": automatic_school_year,
                "calendars": calendars,
                "existing_mappings": [],
            },
            status_code=400,
        )

    client = MSHSAAClient(get_settings())
    try:
        result = await client.fetch_activity_schedule(school.mshsaa_url, activity_id, year_value)
        schedulable_row_count = sum(1 for row in result["rows"] if row_has_schedulable_date(row))
        if schedulable_row_count == 0:
            kind = "success"
            message = (
                "MSHSAA returned this activity, but it does not have any schedulable event dates yet. "
                "You can still pair it to a Google Calendar now, and AthletiSync will begin syncing once events are posted."
            )
        else:
            kind = "success"
            message = f"Loaded {schedulable_row_count} schedulable event row(s) from MSHSAA."
    except Exception as exc:  # pragma: no cover - network-dependent UI path
        result = {"rows": [], "schedule_url": None}
        kind = "error"
        message = f"Could not load schedule data: {exc}"

    existing_mappings = db.scalars(
        select(SyncMapping)
        .options(
            joinedload(SyncMapping.school_year),
            joinedload(SyncMapping.school),
            joinedload(SyncMapping.sport),
            joinedload(SyncMapping.level),
            joinedload(SyncMapping.google_calendar),
        )
        .where(
            SyncMapping.school_id == school_id,
            SyncMapping.source_activity_id == activity_id,
        )
        .order_by(SyncMapping.id.desc())
    ).all()

    return request.app.state.templates.TemplateResponse(
        request,
        "partials/mshsaa_schedule.html",
        {
            "request": request,
            "kind": kind,
            "message": message,
            "rows": [_with_calendar_preview(row, result.get("school_year")) for row in result["rows"]],
            "level_names": sorted({row["level_name"] for row in result["rows"] if row["level_name"]}),
            "school": school,
            "activity_name": activity_name,
            "activity_id": activity_id,
            "schedule_url": result["schedule_url"],
            "school_year": result.get("school_year"),
            "has_schedulable_rows": any(row_has_schedulable_date(row) for row in result["rows"]),
            "automatic_school_year": automatic_school_year,
            "calendars": calendars,
            "existing_mappings": existing_mappings,
        },
    )


@router.post("/{school_id}/activities/import", response_class=HTMLResponse)
def import_activity(
    school_id: int,
    request: Request,
    csrf_token: str = Form(...),
    activity_name: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    sport, created = ensure_sport(db, activity_name.strip())
    message = (
        f"Imported sport '{sport.name}' into the catalog."
        if created
        else f"Sport '{sport.name}' already exists in the catalog."
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/banner.html",
        {"request": request, "kind": "success", "message": message},
    )


def _with_calendar_preview(row: dict, school_year_label: str | None) -> dict:
    calendar_date = _calendar_preview_date(row.get("date"), school_year_label)
    enriched = dict(row)
    enriched["calendar_date"] = calendar_date
    return enriched


def _calendar_preview_date(date_text: str | None, school_year_label: str | None) -> str:
    if not date_text or not school_year_label:
        return ""
    try:
        month_text, day_text = [part.strip() for part in date_text.split("/", 1)]
        start_year = int(school_year_label.split("-")[0])
        month = int(month_text)
        day = int(day_text)
        year = start_year if month >= 7 else start_year + 1
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except (ValueError, IndexError):
        return ""


@router.post("/{school_id}/levels/import", response_class=HTMLResponse)
def import_level(
    school_id: int,
    request: Request,
    csrf_token: str = Form(...),
    level_name: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    level, created = ensure_level(db, level_name.strip())
    message = (
        f"Imported level '{level.name}' into the catalog."
        if created
        else f"Level '{level.name}' already exists in the catalog."
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/banner.html",
        {"request": request, "kind": "success", "message": message},
    )
