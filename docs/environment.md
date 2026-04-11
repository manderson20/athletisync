# Environment Variables

- `APP_SECRET_KEY`: session signing key. Required for production.
- `APP_DEBUG`: enables debug mode.
- `APP_HOST`: bind host.
- `APP_PORT`: bind port.
- `DATABASE_URL`: SQLAlchemy database URL. Defaults to SQLite.
- `TIMEZONE`: default district timezone.
- `SCHEDULER_ENABLED`: enable APScheduler background polling.
- `SCHEDULER_TIMEZONE`: scheduler timezone.
- `DEFAULT_ADMIN_USERNAME`: bootstrap admin username.
- `DEFAULT_ADMIN_PASSWORD`: bootstrap admin password.
- `MSHSAA_BASE_URL`: base URL for MSHSAA integration.
- `REQUEST_TIMEOUT_SECONDS`: timeout for provider HTTP requests.
