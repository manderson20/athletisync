from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.integrations.mshsaa import build_source_event_key
from app.models import AppSetting, SourceEvent, SyncedEvent, SyncMapping, SyncRun, SyncRunItem
from app.schemas import NormalizedEvent
from app.services.google_calendar import (
    DryRunCalendarGateway,
    GoogleCalendarGateway,
    build_event_payload,
    event_fingerprint,
)


class SyncService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run_manual_sync(self) -> SyncRun:
        run = SyncRun(trigger="manual", status="running")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        settings = self.db.scalar(select(AppSetting)) or AppSetting()
        mappings = self.db.scalars(
            select(SyncMapping)
            .options(
                joinedload(SyncMapping.school_year),
                joinedload(SyncMapping.school),
                joinedload(SyncMapping.sport),
                joinedload(SyncMapping.level),
                joinedload(SyncMapping.google_calendar),
            )
            .where(SyncMapping.enabled.is_(True))
        ).all()

        gateway = DryRunCalendarGateway()
        for mapping in mappings:
            sample_events = self._sample_events(mapping)
            for event in sample_events:
                mapping_gateway = self._gateway_for_mapping(mapping)
                self._sync_event(run, mapping, event, mapping_gateway, settings.event_description_template)

        run.summary_json = {
            "last_completed_at": datetime.now(UTC).isoformat(),
            "mappings_processed": len(mappings),
        }
        run.status = "completed" if run.error_count == 0 else "completed_with_errors"
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _sample_events(self, mapping: SyncMapping) -> list[NormalizedEvent]:
        # MVP mode seeds deterministic sample data until the live MSHSAA adapter is wired to district pages.
        return [
            NormalizedEvent(
                source_reference=f"{mapping.id}-sample-1",
                title=f"{mapping.school.name} {mapping.sport.name if mapping.sport else 'Activity'}",
                opponent="Sample Opponent",
                location="Main Gym",
                start_at=datetime(2026, 9, 1, 18, 0, tzinfo=UTC),
                end_at=datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
                payload={"source": "sample"},
            )
        ]

    def _gateway_for_mapping(self, mapping: SyncMapping):
        profile = mapping.google_calendar.auth_profile if mapping.google_calendar else None
        if profile and profile.service_account_json.strip():
            try:
                return GoogleCalendarGateway(profile)
            except Exception:
                # Runtime credential issues should not break the entire MVP when calendars are partially configured.
                return DryRunCalendarGateway()
        return DryRunCalendarGateway()

    def _sync_event(
        self,
        run: SyncRun,
        mapping: SyncMapping,
        normalized: NormalizedEvent,
        gateway,
        description_template: str,
    ) -> None:
        key = build_source_event_key(
            mapping.school_year.label,
            mapping.school.name,
            mapping.sport.name if mapping.sport else "general",
            mapping.level.name if mapping.level else "general",
            normalized,
        )
        source_event = self.db.scalar(select(SourceEvent).where(SourceEvent.source_event_key == key))
        if source_event is None:
            source_event = SourceEvent(
                mapping_id=mapping.id,
                source_event_key=key,
                source_reference=normalized.source_reference,
                title=normalized.title,
                opponent=normalized.opponent,
                location=normalized.location,
                start_at=normalized.start_at.replace(tzinfo=None) if normalized.start_at else None,
                end_at=normalized.end_at.replace(tzinfo=None) if normalized.end_at else None,
                is_all_day=normalized.is_all_day,
                status=normalized.status,
                payload=normalized.payload,
            )
            self.db.add(source_event)
            self.db.flush()
        else:
            source_event.title = normalized.title
            source_event.opponent = normalized.opponent
            source_event.location = normalized.location
            source_event.start_at = normalized.start_at.replace(tzinfo=None) if normalized.start_at else None
            source_event.end_at = normalized.end_at.replace(tzinfo=None) if normalized.end_at else None
            source_event.is_all_day = normalized.is_all_day
            source_event.status = normalized.status
            source_event.payload = normalized.payload
            source_event.last_seen_at = datetime.utcnow()

        synced = self.db.scalar(select(SyncedEvent).where(SyncedEvent.source_event_id == source_event.id))
        before_fingerprint = synced.fingerprint if synced else None
        fingerprint = event_fingerprint(source_event)
        action = "skipped"

        if not mapping.google_calendar:
            run.skipped_count += 1
            message = f"{source_event.title} skipped because the mapping has no Google Calendar destination."
        elif synced is not None and before_fingerprint == fingerprint:
            run.skipped_count += 1
            message = f"{source_event.title} skipped because no changes were detected."
        else:
            payload = build_event_payload(mapping, source_event, description_template)
            google_id = gateway.upsert_event(
                mapping.google_calendar.calendar_id,
                synced.google_event_id if synced else None,
                payload,
            )
            if synced is None:
                synced = SyncedEvent(
                    source_event_id=source_event.id,
                    google_event_id=google_id,
                    calendar_id=mapping.google_calendar.calendar_id,
                    fingerprint=fingerprint,
                )
                self.db.add(synced)
                run.created_count += 1
                action = "created"
            else:
                synced.google_event_id = google_id
                synced.fingerprint = fingerprint
                synced.last_synced_at = datetime.utcnow()
                run.updated_count += 1
                action = "updated"
            message = f"{source_event.title} {action}."

        self.db.add(
            SyncRunItem(
                sync_run_id=run.id,
                source_event_key=source_event.source_event_key,
                action=action,
                status="ok",
                message=message,
            )
        )
        self.db.commit()
