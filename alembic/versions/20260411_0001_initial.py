"""Initial AthletiSync schema."""

from alembic import op
import sqlalchemy as sa

revision = "20260411_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("district_name", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("polling_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("default_school_year_label", sa.String(length=16), nullable=False),
        sa.Column("event_description_template", sa.Text(), nullable=False),
        sa.Column("cancellation_behavior", sa.String(length=32), nullable=False),
        sa.Column("sync_retry_count", sa.Integer(), nullable=False),
        sa.Column("log_retention_days", sa.Integer(), nullable=False),
    )
    op.create_table(
        "google_auth_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("service_account_json", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "school_years",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(length=16), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("external_id", sa.String(length=64), nullable=True),
        sa.Column("mshsaa_url", sa.String(length=255), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_schools_external_id", "schools", ["external_id"])
    op.create_table(
        "sports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=128), nullable=False, unique=True),
    )
    op.create_table(
        "sport_levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=128), nullable=False, unique=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table(
        "google_calendars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auth_profile_id", sa.Integer(), sa.ForeignKey("google_auth_profiles.id"), nullable=True),
        sa.Column("calendar_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "sync_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_year_id", sa.Integer(), sa.ForeignKey("school_years.id"), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("sport_id", sa.Integer(), sa.ForeignKey("sports.id"), nullable=True),
        sa.Column("level_id", sa.Integer(), sa.ForeignKey("sport_levels.id"), nullable=True),
        sa.Column("google_calendar_id", sa.Integer(), sa.ForeignKey("google_calendars.id"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sync_behavior", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "school_year_id",
            "school_id",
            "sport_id",
            "level_id",
            "google_calendar_id",
            name="uq_mapping_dimension",
        ),
    )
    op.create_table(
        "source_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mapping_id", sa.Integer(), sa.ForeignKey("sync_mappings.id"), nullable=False),
        sa.Column("source_event_key", sa.String(length=255), nullable=False, unique=True),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("opponent", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("start_at", sa.DateTime(), nullable=True),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("is_all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_source_events_source_event_key", "source_events", ["source_event_key"])
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("removed_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "synced_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_event_id", sa.Integer(), sa.ForeignKey("source_events.id"), nullable=False, unique=True),
        sa.Column("google_event_id", sa.String(length=255), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "sync_run_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sync_run_id", sa.Integer(), sa.ForeignKey("sync_runs.id"), nullable=False),
        sa.Column("source_event_key", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sync_run_items")
    op.drop_table("synced_events")
    op.drop_table("sync_runs")
    op.drop_index("ix_source_events_source_event_key", table_name="source_events")
    op.drop_table("source_events")
    op.drop_table("sync_mappings")
    op.drop_table("google_calendars")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_table("sport_levels")
    op.drop_table("sports")
    op.drop_index("ix_schools_external_id", table_name="schools")
    op.drop_table("schools")
    op.drop_table("school_years")
    op.drop_table("google_auth_profiles")
    op.drop_table("app_settings")
