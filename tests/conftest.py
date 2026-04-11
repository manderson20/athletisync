from __future__ import annotations

import os
from pathlib import Path

TEST_DB_PATH = Path("/tmp/athletisync-test.db")

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")
os.environ.setdefault("APP_SECRET_KEY", "test-secret")
os.environ.setdefault("DEFAULT_ADMIN_USERNAME", "admin")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "ChangeMe123!")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
