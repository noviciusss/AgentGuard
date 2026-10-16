"""Release-profile tests for root and standalone package metadata."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def _metadata(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_root_bundle_owns_all_official_phase5_entry_points() -> None:
    metadata = _metadata("pyproject.toml")

    for entry_point in (
        'langgraph = "agentguard_langgraph:Plugin"',
        'graph = "agentguard_graph:Plugin"',
        'owasp = "agentguard_owasp:Plugin"',
        'llm_triage = "agentguard_llm_triage:Plugin"',
        'trace = "agentguard_trace:Plugin"',
    ):
        assert entry_point in metadata


def test_standalone_plugins_depend_on_core_not_the_bundle() -> None:
    for package in (
        "agentguard-graph",
        "agentguard-owasp",
        "agentguard-llm-triage",
        "agentguard-trace",
    ):
        metadata = _metadata(f"packages/{package}/pyproject.toml")
        assert 'dependencies = ["agentguard-core>=0.1"]' in metadata
        assert 'dependencies = ["agentguard>=0.1"]' not in metadata


def test_distribution_documentation_describes_mutually_exclusive_profiles() -> None:
    documentation = _metadata("docs/distribution.md")

    assert "Profile A: bundled CLI" in documentation
    assert "Profile B: core plus selected plugins" in documentation
    assert "not intended to be installed together" in documentation


def test_server_distribution_is_separate_from_offline_core() -> None:
    metadata = _metadata("packages/agentguard-server/pyproject.toml")

    assert 'name = "agentguard-server"' in metadata
    assert '"fastapi>=0.115,<1"' in metadata
    assert '"psycopg[binary]>=3.2,<4"' in metadata
    assert '"sqlalchemy>=2,<3"' in metadata
    assert '"alembic>=1.13,<2"' in metadata
    assert "agentguard-core" not in metadata


def test_dashboard_has_a_locked_node_dependency_graph() -> None:
    package = _metadata("web/package.json")
    lockfile = ROOT / "web/package-lock.json"

    assert '"scripts"' in package
    assert '"test": "tsc --noEmit"' in package
    assert lockfile.exists()
