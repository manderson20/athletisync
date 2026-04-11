from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.dependencies import require_user
from app.integrations.mshsaa import MSHSAAClient
from app.models import School
from app.security import ensure_csrf_token, verify_csrf
from app.services.catalog import ensure_level, ensure_sport

router = APIRouter(prefix="/schools", tags=["schools"])


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
    source_url = school.mshsaa_url
    kind = "success"
    message = "Review the discovered activities and choose one to inspect."

    if not school.mshsaa_url:
        kind = "error"
        message = "Add an MSHSAA URL to this school before reviewing the source."
    else:
        client = MSHSAAClient(get_settings())
        try:
            result = await client.fetch_activity_catalog(school.mshsaa_url)
            activities = result["activities"]
            school_year = result["school_year"]
            source_url = result["source_url"]
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
            "source_url": source_url,
            "kind": kind,
            "message": message,
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


@router.post("/{school_id}/preview", response_class=HTMLResponse)
async def preview_school_source(
    school_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    school = db.get(School, school_id)
    if not school or not school.mshsaa_url:
        return request.app.state.templates.TemplateResponse(
            request,
            "partials/mshsaa_preview.html",
            {
                "request": request,
                "kind": "error",
                "message": "Add an MSHSAA URL to the school before testing the source.",
                "activities": [],
                "school": school,
            },
            status_code=400,
        )

    client = MSHSAAClient(get_settings())
    try:
        result = await client.fetch_activity_catalog(school.mshsaa_url)
        activities = result["activities"]
        kind = "success"
        message = f"Loaded {len(activities)} activities from the configured MSHSAA source."
    except Exception as exc:  # pragma: no cover - network-dependent UI path
        activities = []
        result = {"school_year": None, "source_url": school.mshsaa_url}
        kind = "error"
        message = f"Could not load MSHSAA data: {exc}"

    return request.app.state.templates.TemplateResponse(
        request,
        "partials/mshsaa_preview.html",
        {
            "request": request,
            "kind": kind,
            "message": message,
            "activities": activities,
            "school_year": result["school_year"],
            "source_url": result["source_url"],
            "school": school,
        },
    )


@router.post("/{school_id}/activities/{activity_id}/schedule", response_class=HTMLResponse)
async def preview_activity_schedule(
    school_id: int,
    activity_id: str,
    request: Request,
    csrf_token: str = Form(...),
    activity_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    school = db.get(School, school_id)
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
                "schedule_url": None,
            },
            status_code=400,
        )

    client = MSHSAAClient(get_settings())
    try:
        result = await client.fetch_activity_schedule(school.mshsaa_url, activity_id)
        kind = "success"
        message = f"Loaded {len(result['rows'])} schedule rows from MSHSAA."
    except Exception as exc:  # pragma: no cover - network-dependent UI path
        result = {"rows": [], "schedule_url": None}
        kind = "error"
        message = f"Could not load schedule data: {exc}"

    return request.app.state.templates.TemplateResponse(
        request,
        "partials/mshsaa_schedule.html",
        {
            "request": request,
            "kind": kind,
            "message": message,
            "rows": result["rows"],
            "level_names": sorted({row["level_name"] for row in result["rows"] if row["level_name"]}),
            "school": school,
            "activity_name": activity_name,
            "schedule_url": result["schedule_url"],
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
