from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.dependencies import require_user
from app.models import AppSetting, GoogleCalendar, School, SyncMapping, SyncRun
from app.security import ensure_csrf_token

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    settings = db.scalar(select(AppSetting)) or AppSetting()
    recent_runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(5)).all()
    latest_run = recent_runs[0] if recent_runs else None
    mappings = db.scalars(
        select(SyncMapping)
        .options(
            joinedload(SyncMapping.school_year),
            joinedload(SyncMapping.school),
            joinedload(SyncMapping.sport),
            joinedload(SyncMapping.level),
            joinedload(SyncMapping.google_calendar),
        )
        .order_by(SyncMapping.id.desc())
    ).all()
    context = {
        "request": request,
        "settings": settings,
        "schools": db.scalars(select(School).order_by(School.name)).all(),
        "mappings": mappings,
        "calendars": db.scalars(select(GoogleCalendar).order_by(GoogleCalendar.display_name)).all(),
        "recent_runs": recent_runs,
        "latest_run": latest_run,
        "next_sync_minutes": settings.polling_interval_minutes,
        "csrf_token": ensure_csrf_token(request),
    }
    return request.app.state.templates.TemplateResponse(request, "dashboard/index.html", context)
