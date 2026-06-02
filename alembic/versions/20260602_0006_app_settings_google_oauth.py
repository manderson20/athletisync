"""Add Google OAuth settings to app settings

Revision ID: 20260602_0006
Revises: 20260602_0005
Create Date: 2026-06-02 00:06:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260602_0006"
down_revision = "20260602_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("google_oauth_client_id", sa.String(length=255), nullable=True))
    op.add_column("app_settings", sa.Column("google_oauth_client_secret", sa.Text(), nullable=True))
    op.add_column("app_settings", sa.Column("google_oauth_redirect_uri", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("app_settings", "google_oauth_redirect_uri")
    op.drop_column("app_settings", "google_oauth_client_secret")
    op.drop_column("app_settings", "google_oauth_client_id")
