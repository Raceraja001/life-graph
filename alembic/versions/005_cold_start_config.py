"""Add cold_start_config to tenant_configs.

Revision ID: 005
Revises: 004

Adds JSONB column for per-tenant cold start configuration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_configs",
        sa.Column(
            "cold_start_config",
            JSONB,
            nullable=True,
            comment="Per-tenant cold start questions/config. Null = use defaults.",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_configs", "cold_start_config")
