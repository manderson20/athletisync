# Setup Instructions

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The initial admin account is created from `.env` if no users exist.

## First Login Checklist

- Change the default admin password immediately.
- Set the district name and timezone on the settings page.
- Add one or more schools with MSHSAA references.
- Add Google auth profile(s) and calendar destinations.
- Create mapping rows for school year, school, sport, level, and calendar destination combinations.
