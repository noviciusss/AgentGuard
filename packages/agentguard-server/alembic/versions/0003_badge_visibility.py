"""Add explicit repository-scoped badge visibility."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_badge_visibility"
down_revision: str | None = "0002_webhook_deliveries"
branch_labels: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column(
            "badge_public", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("repositories", "badge_public")
