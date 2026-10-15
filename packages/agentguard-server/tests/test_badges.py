"""Coverage for deterministic and privacy-safe public badge helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast

import pytest

from agentguard_server.badges import (
    BadgeFormat,
    BadgeResponse,
    BadgeStatus,
    BadgeVisibility,
    FindingCounts,
    RiskLevel,
    build_badge_response,
    calculate_risk_level,
    render_badge,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        (FindingCounts(), RiskLevel.PASSING),
        (FindingCounts(infos=1), RiskLevel.LOW),
        (FindingCounts(infos=9), RiskLevel.LOW),
        (FindingCounts(warnings=1), RiskLevel.MEDIUM),
        (FindingCounts(warnings=9), RiskLevel.MEDIUM),
        (FindingCounts(infos=10), RiskLevel.MEDIUM),
        (FindingCounts(warnings=10), RiskLevel.HIGH),
        (FindingCounts(errors=1), RiskLevel.HIGH),
        (FindingCounts(errors=1, warnings=1, infos=1), RiskLevel.HIGH),
    ],
)
def test_calculate_risk_level_uses_severity_and_count_thresholds(
    counts: FindingCounts, expected: RiskLevel
) -> None:
    assert calculate_risk_level(counts) is expected


def test_counts_mapping_is_normalized_without_discarding_unknown_severities() -> None:
    counts = FindingCounts.from_severity_counts({" ERROR ": 1, "Warning": 2, "info": 3})

    assert counts == FindingCounts(errors=1, warnings=2, infos=3)
    assert counts.as_dict() == {"error": 1, "warning": 2, "info": 3}

    with pytest.raises(ValueError, match="unsupported severity"):
        FindingCounts.from_severity_counts({"critical": 1})


def test_equivalent_inputs_have_identical_json_svg_and_cache_metadata() -> None:
    first = build_badge_response(
        FindingCounts.from_severity_counts({"warning": 2}),
        now=NOW,
        updated_at=NOW - timedelta(hours=1),
    )
    second = build_badge_response(
        FindingCounts(warnings=2),
        now=NOW,
        updated_at=NOW - timedelta(hours=1),
    )

    assert first.status is BadgeStatus.AVAILABLE
    assert first.to_json() == second.to_json()
    assert first.render_svg() == second.render_svg()
    assert first.etag == second.etag
    assert first.headers() == second.headers()
    assert first.headers()["Cache-Control"] == "public, max-age=300, must-revalidate"
    assert first.headers(media_type="application/json")["Content-Type"] == (
        "application/json"
    )


def test_stale_data_is_explicit_and_has_shorter_cache_lifetime() -> None:
    response = build_badge_response(
        FindingCounts(errors=1),
        now=NOW,
        updated_at=NOW - timedelta(days=8),
    )

    assert response.status is BadgeStatus.STALE
    assert response.risk_level is RiskLevel.HIGH
    assert response.label == "risk: high (stale)"
    assert response.headers()["Cache-Control"] == (
        "public, max-age=60, must-revalidate"
    )


@pytest.mark.parametrize(
    ("response", "status", "label"),
    [
        (
            build_badge_response(None, now=NOW),
            BadgeStatus.MISSING,
            "risk: no data",
        ),
        (
            build_badge_response(FindingCounts(errors=1), now=NOW, unavailable=True),
            BadgeStatus.UNAVAILABLE,
            "risk: unavailable",
        ),
        (
            build_badge_response(FindingCounts(errors=1), now=NOW, updated_at=None),
            BadgeStatus.UNAVAILABLE,
            "risk: unavailable",
        ),
        (
            build_badge_response(
                FindingCounts(errors=1),
                now=NOW,
                visibility=BadgeVisibility.PRIVATE,
            ),
            BadgeStatus.PRIVATE,
            "risk: private",
        ),
    ],
)
def test_missing_private_and_unavailable_states_are_generic_and_redacted(
    response: BadgeResponse, status: BadgeStatus, label: str
) -> None:
    assert response.status is status
    assert response.label == label
    assert response.risk_level is None
    assert response.counts is None
    assert response.to_json() == response.render("json")
    assert "source" not in response.to_json().lower()
    assert "snippet" not in response.to_json().lower()
    assert "agent.py" not in response.render_svg()
    assert "missing timeout" not in response.render_svg()


def test_private_and_unavailable_responses_cannot_be_publicly_cached() -> None:
    private = build_badge_response(
        FindingCounts(errors=5),
        now=NOW,
        updated_at=NOW,
        visibility=BadgeVisibility.PRIVATE,
    )
    unavailable = build_badge_response(
        FindingCounts(errors=5),
        now=NOW,
        updated_at=NOW,
        unavailable=True,
    )

    assert private.headers()["Cache-Control"] == "private, no-store"
    assert unavailable.headers()["Cache-Control"] == (
        "public, max-age=30, must-revalidate"
    )
    assert '"counts":null' in private.to_json()
    assert '"counts":null' in unavailable.to_json()


def test_render_badge_rejects_unknown_format() -> None:
    response = build_badge_response(FindingCounts(), now=NOW, updated_at=NOW)

    assert render_badge(response, "json") == response.to_json()
    with pytest.raises(ValueError, match="unsupported badge format"):
        render_badge(response, cast(BadgeFormat, "text"))
