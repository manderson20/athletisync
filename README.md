# AthletiSync

AthletiSync is a lightweight self-hosted web application that syncs MSHSAA athletic schedules into Google Calendar. It is designed for district staff who want MSHSAA to remain the source of truth while publishing schedules to one or more Google Calendars.

## Current MVP

Version: `0.1.0`

The current MVP includes:

- FastAPI backend with Jinja templates, HTMX interactions, and minimal JavaScript
- Session-based admin authentication with password hashing and CSRF protection
- SQLite + SQLAlchemy + Alembic schema bootstrap
- Admin pages for dashboard, schools, sync mappings, Google destinations, settings, and sync history
- Mapping-based sync model for school year, school, sport, level, and calendar combinations
- APScheduler-driven background sync plus manual sync execution
- MSHSAA parser abstraction and Google Calendar gateway abstraction
- Docker and Docker Compose deployment baseline
- Tests for parsing, source identity generation, and Google payload composition

## Quick Start

1. Create a virtual environment and install dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

2. Copy the environment file and adjust secrets.

```bash
cp .env.example .env
```

3. Run Alembic migrations.

```bash
alembic upgrade head
```

4. Start the app.

```bash
uvicorn app.main:app --reload
```

5. Log in with the admin username/password from `.env`.

## Project Structure

- `app/`: FastAPI app, routes, services, templates, static assets, models, and configuration
- `alembic/`: migration environment and initial schema
- `tests/`: pytest coverage for core logic
- `docs/`: deployment, architecture, admin usage, and integration guides
- `version`: current app version
- `Changelog`: release history

## Versioning

AthletiSync keeps version metadata in the `version` file using `MAJOR.MINOR.PATCH` format.

- Increment `PATCH` for fixes and small internal improvements.
- Increment `MINOR` for new backward-compatible features.
- Increment `MAJOR` for breaking changes.

Each versioned change should also be recorded in `Changelog`.

## MVP Notes

- The sync service currently uses deterministic sample events while district-specific MSHSAA source pages are being configured.
- The MSHSAA parsing layer is isolated so live provider adapters can be hardened without changing mapping, storage, or Google sync logic.
- The Google Calendar integration supports service-account-based access when installed with the `google` dependency extra.

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Setup Guide](docs/setup.md)
- [Environment Variables](docs/environment.md)
- [Google Calendar Guide](docs/google-calendar.md)
- [Admin Usage Guide](docs/admin-guide.md)
- [Development Guide](docs/development.md)
- [Ubuntu Deployment Guide](docs/ubuntu-deployment.md)

## GitHub Metadata

Suggested repository name: `athletisync`

Suggested short description:

`Lightweight self-hosted app that syncs MSHSAA athletic schedules to Google Calendar.`
