"""Create the initial AgentGuard Server schema."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None


def _id(*, primary_key: bool = False) -> sa.Column[object]:
    return sa.Column(
        "id", sa.Uuid(as_uuid=True), nullable=False, primary_key=primary_key
    )


def _created_at() -> sa.Column[object]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def upgrade() -> None:
    op.create_table(
        "repositories",
        _id(primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "provider", "full_name", name="uq_repositories_provider_name"
        ),
    )
    op.create_table(
        "branches",
        _id(primary_key=True),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "repository_id", "name", name="uq_branches_repository_name"
        ),
    )
    op.create_table(
        "commits",
        _id(primary_key=True),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sha", sa.String(length=128), nullable=False),
        sa.Column("message", sa.String(length=1000)),
        sa.Column("authored_at", sa.DateTime(timezone=True)),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("repository_id", "sha", name="uq_commits_repository_sha"),
    )
    op.create_table(
        "scans",
        _id(primary_key=True),
        sa.Column("scan_key", sa.String(length=255), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("branch_id", sa.Uuid(as_uuid=True)),
        sa.Column("commit_id", sa.Uuid(as_uuid=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("analyzer_version", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("details", sa.JSON(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"]),
        sa.UniqueConstraint("scan_key", name="uq_scans_scan_key"),
    )
    op.create_index("ix_scans_created_at_id", "scans", ["created_at", "id"])
    op.create_table(
        "findings",
        _id(primary_key=True),
        sa.Column("scan_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("rule_id", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("why", sa.String(length=2000), nullable=False),
        sa.Column("suggestion", sa.String(length=2000), nullable=False),
        sa.Column("file", sa.String(length=1000), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("col", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("end_col", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "scan_id", "fingerprint", name="uq_findings_scan_fingerprint"
        ),
    )
    op.create_index("ix_findings_rule_id", "findings", ["rule_id"])
    op.create_table(
        "baselines",
        _id(primary_key=True),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("fingerprints", sa.JSON(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "repository_id", "name", name="uq_baselines_repository_name"
        ),
    )
    op.create_table(
        "plugins",
        _id(primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("entry_point", sa.String(length=500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        _created_at(),
        sa.UniqueConstraint("name", "version", name="uq_plugins_name_version"),
    )
    op.create_table(
        "configuration_versions",
        _id(primary_key=True),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "repository_id",
            "version",
            name="uq_config_versions_repository_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("configuration_versions")
    op.drop_table("plugins")
    op.drop_table("baselines")
    op.drop_index("ix_findings_rule_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_scans_created_at_id", table_name="scans")
    op.drop_table("scans")
    op.drop_table("commits")
    op.drop_table("branches")
    op.drop_table("repositories")
