from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_user
from app.models import SchoolYear
from app.security import ensure_csrf_token, verify_csrf

router = APIRouter(prefix="/school-years", tags=["school-years"])


@router.get("", response_class=HTMLResponse)
def school_years_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    return request.app.state.templates.TemplateResponse(
        request,
        "school_years/index.html",
        {
            "request": request,
            "school_years": db.scalars(select(SchoolYear).order_by(SchoolYear.label.desc())).all(),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("")
def create_school_year(
    request: Request,
    label: str = Form(...),
    is_active: str | None = Form(default=None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    normalized_label = label.strip()
    existing = db.scalar(select(SchoolYear).where(SchoolYear.label == normalized_label))
    if existing is None:
        db.add(SchoolYear(label=normalized_label, is_active=is_active == "on"))
        db.commit()
    return RedirectResponse("/school-years", status_code=303)
