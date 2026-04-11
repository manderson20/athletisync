from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AppSetting, SchoolYear, SportLevel, User
from app.security import hash_password


def bootstrap_defaults(db: Session, settings: Settings) -> None:
    # Seed the minimum records needed for a first usable login and dashboard.
    if db.scalar(select(AppSetting)):
        return

    db.add(
        AppSetting(
            district_name="AthletiSync District",
            timezone=settings.timezone,
            default_school_year_label="2025-2026",
        )
    )
    db.add(SchoolYear(label="2025-2026", is_active=True))
    db.add(
        User(
            username=settings.default_admin_username,
            password_hash=hash_password(settings.default_admin_password),
        )
    )
    for name, slug in [
        ("Varsity", "varsity"),
        ("Junior Varsity", "junior-varsity"),
        ("C Team", "c-team"),
        ("Middle School", "middle-school"),
    ]:
        db.add(SportLevel(name=name, slug=slug))
    db.commit()
