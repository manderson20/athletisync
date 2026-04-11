import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Sport, SportLevel


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def ensure_sport(db: Session, name: str) -> tuple[Sport, bool]:
    existing = db.scalar(select(Sport).where(Sport.name == name))
    if existing:
        return existing, False

    base_slug = slugify(name)
    slug = _next_unique_slug(db, Sport, base_slug)
    sport = Sport(name=name, slug=slug)
    db.add(sport)
    db.commit()
    db.refresh(sport)
    return sport, True


def ensure_level(db: Session, name: str) -> tuple[SportLevel, bool]:
    existing = db.scalar(select(SportLevel).where(SportLevel.name == name))
    if existing:
        return existing, False

    base_slug = slugify(name)
    slug = _next_unique_slug(db, SportLevel, base_slug)
    level = SportLevel(name=name, slug=slug)
    db.add(level)
    db.commit()
    db.refresh(level)
    return level, True


def _next_unique_slug(db: Session, model, base_slug: str) -> str:
    slug = base_slug
    index = 2
    while db.scalar(select(model).where(model.slug == slug)):
        slug = f"{base_slug}-{index}"
        index += 1
    return slug
