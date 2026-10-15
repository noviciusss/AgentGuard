"""Declarative model and constraint coverage."""

from agentguard_server.models import Base


def test_initial_model_set_and_idempotency_constraints_exist() -> None:
    expected_tables = {
        "repositories",
        "branches",
        "commits",
        "scans",
        "findings",
        "baselines",
        "plugins",
        "configuration_versions",
        "webhook_deliveries",
        "audit_records",
    }
    assert set(Base.metadata.tables) == expected_tables

    constraints = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if constraint.name is not None
    }
    assert {
        "uq_repositories_provider_name",
        "uq_branches_repository_name",
        "uq_commits_repository_sha",
        "uq_scans_scan_key",
        "uq_findings_scan_fingerprint",
        "uq_baselines_repository_name",
        "uq_plugins_name_version",
        "uq_config_versions_repository_version",
    } <= constraints
