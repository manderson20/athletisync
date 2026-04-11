from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SyncMapping
from app.schemas import MappingFormData


def upsert_mapping(db: Session, payload: MappingFormData) -> SyncMapping:
    query = select(SyncMapping).where(
        SyncMapping.school_year_id == payload.school_year_id,
        SyncMapping.school_id == payload.school_id,
        SyncMapping.sport_id.is_(payload.sport_id) if payload.sport_id is None else SyncMapping.sport_id == payload.sport_id,
        SyncMapping.level_id.is_(payload.level_id) if payload.level_id is None else SyncMapping.level_id == payload.level_id,
        SyncMapping.google_calendar_id.is_(payload.google_calendar_id)
        if payload.google_calendar_id is None
        else SyncMapping.google_calendar_id == payload.google_calendar_id,
    )
    mapping = db.scalar(query)
    if mapping is None:
        mapping = SyncMapping(**payload.model_dump())
        db.add(mapping)
    else:
        for key, value in payload.model_dump().items():
            setattr(mapping, key, value)

    db.commit()
    db.refresh(mapping)
    return mapping
