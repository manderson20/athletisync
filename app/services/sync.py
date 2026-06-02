from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.integrations.mshsaa import MSHSAAClient, build_source_event_key
from app.models import AppSetting, SchoolYear, SourceEvent, SyncedEvent, SyncMapping, SyncRun, SyncRunItem
from app.schemas import NormalizedEvent
from app.services.google_calendar import (
    DryRunCalendarGateway,
    GoogleCalendarGateway,
    build_event_payload,
    event_fingerprint,
)
from app.services.school_years import current_school_year_label, is_automatic_school_year
from app.services.school_years import discover_and_ensure_school_years


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

        for mapping in mappings:
            live_events = asyncio.run(self._fetch_mapping_events(mapping, settings))
            for event in live_events:
                mapping_gateway = self._gateway_for_mapping(mapping)
                self._sync_event(run, mapping, event, mapping_gateway, settings)

        run.summary_json = {
            "last_completed_at": datetime.now(UTC).isoformat(),
            "mappings_processed": len(mappings),
        }
        run.status = "completed" if run.error_count == 0 else "completed_with_errors"
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(run)
        return run

    async def _fetch_mapping_events(self, mapping: SyncMapping, app_settings: AppSetting) -> list[NormalizedEvent]:
        if not mapping.school.mshsaa_url or not mapping.sport:
            return []

        runtime_settings = get_settings()
        client = MSHSAAClient(runtime_settings)
        catalog = await client.fetch_activity_catalog(mapping.school.mshsaa_url)
        discover_and_ensure_school_years(self.db, catalog.get("available_school_years", []))

        matching_activities = self._matching_activities(mapping, catalog.get("activities", []))
        if not matching_activities:
            return []

        events: list[NormalizedEvent] = []
        for activity in matching_activities:
            default_schedule = await client.fetch_activity_schedule(
                mapping.school.mshsaa_url,
                activity["external_id"],
            )
            year_options = default_schedule.get("school_year_options", []) or catalog.get("school_year_options", [])
            if year_options:
                discover_and_ensure_school_years(self.db, [item["label"] for item in year_options])

            target_year_options = self._target_year_options(mapping, year_options)
            default_year_label = default_schedule.get("school_year")
            if not target_year_options:
                target_year_options = catalog.get("school_year_options", [])

            for year_option in target_year_options:
                if year_option.get("label") == default_year_label:
                    schedule = default_schedule
                else:
                    schedule = await client.fetch_activity_schedule(
                        mapping.school.mshsaa_url,
                        activity["external_id"],
                        year_option["value"],
                    )
                for row in schedule["rows"]:
                    if mapping.level and row["level_name"] != mapping.level.name:
                        continue
                    normalized = self._normalized_event_from_row(
                        mapping,
                        activity,
                        row,
                        schedule.get("school_year"),
                        app_settings.event_title_template,
                    )
                    if normalized:
                        events.append(normalized)
        return events

    def _gateway_for_mapping(self, mapping: SyncMapping):
        profile = mapping.google_calendar.auth_profile if mapping.google_calendar else None
        app_settings = self.db.scalar(select(AppSetting)) or AppSetting()
        if profile and (profile.auth_type == "oauth" or (profile.service_account_json or "").strip()):
            try:
                return GoogleCalendarGateway(profile, app_settings=app_settings)
            except Exception:
                # Runtime credential issues should not break the entire MVP when calendars are partially configured.
                return DryRunCalendarGateway()
        return DryRunCalendarGateway()

    def _matching_activities(self, mapping: SyncMapping, activities: list[dict]) -> list[dict]:
        if mapping.source_activity_id:
            exact_id = [item for item in activities if item["external_id"] == mapping.source_activity_id]
            if exact_id:
                return exact_id

        sport_name = (mapping.sport.name if mapping.sport else "").strip().lower()
        exact = [item for item in activities if item["name"].strip().lower() == sport_name]
        if exact:
            return exact
        return [item for item in activities if sport_name and sport_name in item["name"].strip().lower()]

    def _target_year_options(self, mapping: SyncMapping, options: list[dict[str, str]]) -> list[dict[str, str]]:
        if not options:
            label = self._effective_school_year_label(mapping, None)
            return [{"label": label, "value": label.split("-")[0]}]

        if is_automatic_school_year(mapping.school_year.label):
            current_start = int(current_school_year_label().split("-")[0])
            return [item for item in options if int(item["label"].split("-")[0]) >= current_start]

        target_label = mapping.school_year.label
        matched = [item for item in options if item["label"] == target_label]
        return matched or [{"label": target_label, "value": target_label.split("-")[0]}]

    def _normalized_event_from_row(
        self,
        mapping: SyncMapping,
        activity: dict,
        row: dict,
        school_year_label: str | None,
        event_title_template: str,
    ) -> NormalizedEvent | None:
        start_at, end_at, is_all_day = self._parse_row_datetime(row.get("date"), row.get("score_or_time"), school_year_label)
        if start_at is None:
            return None

        opponent = row.get("opponent") or None
        primary_opponent, participants = self._participant_fields(opponent)
        title = f"{activity['name']} vs {opponent}" if opponent else activity["name"]
        return NormalizedEvent(
            school_year_label=school_year_label or self._effective_school_year_label(mapping, None),
            source_reference=row.get("stable_reference") or row.get("matchup_url") or f"{activity['external_id']}|{row.get('date')}|{opponent}",
            title=title,
            opponent=opponent,
            location=None,
            start_at=start_at,
            end_at=end_at,
            is_all_day=is_all_day,
            payload={
                "source": "mshsaa",
                "school_year_label": school_year_label or self._effective_school_year_label(mapping, None),
                "activity_name": activity["name"],
                "activity_id": activity["external_id"],
                "row_type": row.get("row_type"),
                "primary_opponent": primary_opponent,
                "participants": participants,
                "matchup_url": row.get("matchup_url"),
                "event_title_template": event_title_template,
            },
        )

    def _parse_row_datetime(
        self,
        date_text: str | None,
        score_or_time: str | None,
        school_year_label: str | None,
    ) -> tuple[datetime | None, datetime | None, bool]:
        if not date_text:
            return None, None, True

        school_year = school_year_label or current_school_year_label()
        start_year = int(school_year.split("-")[0])
        month_text, day_text = [part.strip() for part in date_text.split("/", 1)]
        month = int(month_text)
        day = int(day_text)
        year = start_year if month >= 7 else start_year + 1
        tz = ZoneInfo(get_settings().timezone)

        time_text = (score_or_time or "").strip()
        if time_text and any(token in time_text.upper() for token in ["AM", "PM"]):
            parsed_time = datetime.strptime(time_text.upper(), "%I:%M %p")
            start_at = datetime(year, month, day, parsed_time.hour, parsed_time.minute, tzinfo=tz)
            return start_at, None, False

        start_at = datetime(year, month, day, 0, 0, tzinfo=tz)
        return start_at, None, True

    def _sync_event(
        self,
        run: SyncRun,
        mapping: SyncMapping,
        normalized: NormalizedEvent,
        gateway,
        settings: AppSetting,
    ) -> None:
        key = build_source_event_key(
            self._effective_school_year_label(mapping, normalized.school_year_label),
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
            payload = build_event_payload(mapping, source_event, settings)
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

    def _participant_fields(self, opponent: str | None) -> tuple[str, str]:
        full_value = (opponent or "").strip()
        if not full_value:
            return "", ""

        for separator in [",", ";", " / ", " vs "]:
            if separator in full_value:
                primary = full_value.split(separator, 1)[0].strip()
                return primary, full_value
        return full_value, full_value

    def _effective_school_year_label(self, mapping: SyncMapping, event_school_year_label: str | None) -> str:
        if event_school_year_label:
            return event_school_year_label
        if is_automatic_school_year(mapping.school_year.label):
            return current_school_year_label()
        return mapping.school_year.label
