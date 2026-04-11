# Architecture Overview

AthletiSync is a server-rendered FastAPI application designed for a single district first, while keeping the data model and sync engine flexible enough to support additional districts later.

## Layers

- `routes`: request handling, session auth enforcement, form processing, and HTML responses
- `services`: business logic for auth, mapping persistence, bootstrap, scheduler, and sync orchestration
- `integrations`: external-provider specific code such as MSHSAA parsing
- `models`: SQLAlchemy entities for users, settings, calendars, mappings, source events, synced events, and sync runs
- `templates`: Jinja views and HTMX partials for staff-facing administration

## Sync Flow

1. Admin configures schools, calendars, and mappings.
2. Scheduler or manual action triggers a sync run.
3. MSHSAA provider returns source schedule payloads.
4. Source payload is normalized into a provider-independent event schema.
5. Stable source event identity is generated from school year, school, sport, level, and event details.
6. Source events are stored locally and compared against previous sync fingerprints.
7. Google Calendar gateway creates or updates the matching destination event.
8. Sync run and per-event items are stored for observability.

## Mapping Strategy

- Many mappings can target one Google Calendar.
- One mapping can target one dedicated calendar.
- A district can publish all sports to one calendar, one calendar per school, one per sport, or one per school/sport/level.

## Future Extension Points

- Swap `MSHSAAClient` for hardened provider adapters or additional source providers.
- Replace SQLite with PostgreSQL by changing `DATABASE_URL`.
- Support multiple districts by adding a district boundary to configuration and mapping models.
