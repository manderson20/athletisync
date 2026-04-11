from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_user
from app.models import AppSetting, SchoolYear
from app.schemas import SettingsFormData
from app.security import ensure_csrf_token, verify_csrf

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    settings = db.scalar(select(AppSetting)) or AppSetting()
    return request.app.state.templates.TemplateResponse(
        request,
        "settings/index.html",
        {"request": request, "settings": settings, "csrf_token": ensure_csrf_token(request)},
    )


@router.post("")
def save_settings(
    request: Request,
    district_name: str = Form(...),
    timezone: str = Form(...),
    polling_interval_minutes: int = Form(...),
    default_school_year_label: str = Form(...),
    cancellation_behavior: str = Form(...),
    sync_retry_count: int = Form(...),
    log_retention_days: int = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    payload = SettingsFormData(
        district_name=district_name,
        timezone=timezone,
        polling_interval_minutes=polling_interval_minutes,
        default_school_year_label=default_school_year_label,
        cancellation_behavior=cancellation_behavior,
        sync_retry_count=sync_retry_count,
        log_retention_days=log_retention_days,
    )
    settings = db.scalar(select(AppSetting))
    if settings is None:
        settings = AppSetting(**payload.model_dump())
        db.add(settings)
    else:
        for key, value in payload.model_dump().items():
            setattr(settings, key, value)
    school_year = db.scalar(select(SchoolYear).where(SchoolYear.label == payload.default_school_year_label))
    if school_year is None:
        db.add(SchoolYear(label=payload.default_school_year_label, is_active=True))
    db.commit()
    return RedirectResponse("/settings", status_code=303)
