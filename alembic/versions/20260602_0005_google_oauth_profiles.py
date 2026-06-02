"""Add OAuth support for Google auth profiles

Revision ID: 20260602_0005
Revises: 20260411_0004
Create Date: 2026-06-02 00:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260602_0005"
down_revision = "20260411_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "google_auth_profiles",
        sa.Column("auth_type", sa.String(length=32), nullable=False, server_default="service_account"),
    )
    op.add_column("google_auth_profiles", sa.Column("oauth_account_email", sa.String(length=255), nullable=True))
    op.add_column("google_auth_profiles", sa.Column("oauth_refresh_token", sa.Text(), nullable=True))
    op.add_column("google_auth_profiles", sa.Column("oauth_scopes", sa.Text(), nullable=True))

    with op.batch_alter_table("google_auth_profiles") as batch_op:
        batch_op.alter_column("service_account_json", existing_type=sa.Text(), nullable=True)

    op.execute(
        "UPDATE google_auth_profiles SET auth_type = 'service_account' WHERE auth_type IS NULL OR auth_type = ''"
    )


def downgrade() -> None:
    with op.batch_alter_table("google_auth_profiles") as batch_op:
        batch_op.alter_column("service_account_json", existing_type=sa.Text(), nullable=False)

    op.drop_column("google_auth_profiles", "oauth_scopes")
    op.drop_column("google_auth_profiles", "oauth_refresh_token")
    op.drop_column("google_auth_profiles", "oauth_account_email")
    op.drop_column("google_auth_profiles", "auth_type")
