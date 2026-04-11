from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings, get_settings
from app.db.session import Base, SessionLocal, engine
from app.routes import auth, catalog, dashboard, google, mappings, school_years, schools, settings, sync
from app.services.bootstrap import bootstrap_defaults
from app.services.scheduler import build_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings_obj: Settings = app.state.settings
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap_defaults(db, settings_obj)
    finally:
        db.close()

    scheduler = None
    if settings_obj.scheduler_enabled:
        scheduler = build_scheduler(settings_obj)
        scheduler.start()
        app.state.scheduler = scheduler

    yield

    if scheduler:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings_obj = get_settings()
    app = FastAPI(title="AthletiSync", lifespan=lifespan)
    app.state.settings = settings_obj
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    app.state.templates = templates
    templates.env.globals["app_version"] = settings_obj.app_version

    app.add_middleware(SessionMiddleware, secret_key=settings_obj.app_secret_key, same_site="lax", https_only=False)
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok"})

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(schools.router)
    app.include_router(school_years.router)
    app.include_router(catalog.router)
    app.include_router(mappings.router)
    app.include_router(google.router)
    app.include_router(sync.router)
    app.include_router(settings.router)
    return app


app = create_app()
