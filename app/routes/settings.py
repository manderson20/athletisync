from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_user
from app.models import AppSetting
from app.schemas import SettingsFormData
from app.security import ensure_csrf_token, verify_csrf
from app.services.event_formatting import preview_event_format
from app.services.school_years import AUTOMATIC_SCHOOL_YEAR_LABEL, current_school_year_label

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    settings = db.scalar(select(AppSetting)) or AppSetting()
    if settings.default_school_year_label != AUTOMATIC_SCHOOL_YEAR_LABEL:
        settings.default_school_year_label = AUTOMATIC_SCHOOL_YEAR_LABEL
        db.commit()
        db.refresh(settings)
    return request.app.state.templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "request": request,
            "settings": settings,
            "formatter_preview": preview_event_format(settings),
            "automatic_school_year_label": AUTOMATIC_SCHOOL_YEAR_LABEL,
            "current_school_year_label": current_school_year_label(),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("")
def save_settings(
    request: Request,
    district_name: str = Form(...),
    timezone: str = Form(...),
    polling_interval_minutes: int = Form(...),
    event_title_template: str = Form(...),
    event_description_template: str = Form(...),
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
        event_title_template=event_title_template,
        event_description_template=event_description_template,
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
    settings.default_school_year_label = AUTOMATIC_SCHOOL_YEAR_LABEL
    db.commit()
    return RedirectResponse("/settings", status_code=303)


@router.post("/preview-format", response_class=HTMLResponse)
def preview_format(
    request: Request,
    district_name: str = Form(...),
    timezone: str = Form(...),
    polling_interval_minutes: int = Form(...),
    event_title_template: str = Form(...),
    event_description_template: str = Form(...),
    cancellation_behavior: str = Form(...),
    sync_retry_count: int = Form(...),
    log_retention_days: int = Form(...),
    csrf_token: str = Form(...),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    settings = AppSetting(
        district_name=district_name,
        timezone=timezone,
        polling_interval_minutes=polling_interval_minutes,
        event_title_template=event_title_template,
        event_description_template=event_description_template,
        cancellation_behavior=cancellation_behavior,
        sync_retry_count=sync_retry_count,
        log_retention_days=log_retention_days,
        default_school_year_label=AUTOMATIC_SCHOOL_YEAR_LABEL,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/formatter_preview.html",
        {"request": request, "preview": preview_event_format(settings)},
    )
