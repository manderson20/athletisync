from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_user
from app.models import Sport, SportLevel
from app.security import ensure_csrf_token, verify_csrf

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_class=HTMLResponse)
def catalog_page(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    return request.app.state.templates.TemplateResponse(
        "catalog/index.html",
        {
            "request": request,
            "sports": db.scalars(select(Sport).order_by(Sport.name)).all(),
            "levels": db.scalars(select(SportLevel).order_by(SportLevel.name)).all(),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("/sports")
def create_sport(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    db.add(Sport(name=name.strip(), slug=slug.strip()))
    db.commit()
    return RedirectResponse("/catalog", status_code=303)


@router.post("/levels")
def create_level(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_user),
):
    verify_csrf(request, csrf_token)
    db.add(SportLevel(name=name.strip(), slug=slug.strip()))
    db.commit()
    return RedirectResponse("/catalog", status_code=303)
