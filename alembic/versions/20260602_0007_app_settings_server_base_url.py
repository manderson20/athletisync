"""Add server base URL to app settings

Revision ID: 20260602_0007
Revises: 20260602_0006
Create Date: 2026-06-02 00:07:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260602_0007"
down_revision = "20260602_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("server_base_url", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("app_settings", "server_base_url")
