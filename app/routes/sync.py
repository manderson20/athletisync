from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_user
from app.models import SyncRun
from app.security import ensure_csrf_token, verify_csrf
from app.services.sync import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("", response_class=HTMLResponse)
def sync_history(request: Request, db: Session = Depends(get_db), _user=Depends(require_user)):
    runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(20)).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "sync/index.html",
        {"request": request, "runs": runs, "csrf_token": ensure_csrf_token(request)},
    )


@router.post("/run")
def run_sync(request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db), _user=Depends(require_user)):
    verify_csrf(request, csrf_token)
    SyncService(db).run_manual_sync()
    return RedirectResponse("/", status_code=303)
