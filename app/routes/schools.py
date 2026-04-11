from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_user
from app.models import School
from app.security import ensure_csrf_token, verify_csrf

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("", response_class=HTMLResponse)
def schools_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    return request.app.state.templates.TemplateResponse(
        "schools/index.html",
        {
            "request": request,
            "schools": db.scalars(select(School).order_by(School.name)).all(),
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
