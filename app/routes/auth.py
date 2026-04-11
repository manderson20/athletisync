from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import LoginFormData
from app.security import ensure_csrf_token, verify_csrf
from app.services.auth import authenticate_user

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return request.app.state.templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "csrf_token": ensure_csrf_token(request)},
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf_token)
    data = LoginFormData(username=username, password=password)
    user = authenticate_user(db, data.username, data.password)
    if not user:
        return request.app.state.templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid username or password.", "csrf_token": ensure_csrf_token(request)},
            status_code=400,
        )

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
