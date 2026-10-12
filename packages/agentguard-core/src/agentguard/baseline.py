"""Stable finding baselines for incremental CI scans."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from agentguard.findings import Finding


class BaselineError(ValueError):
    """A baseline file is missing, malformed, or unsupported."""


@dataclass(frozen=True)
class Baseline:
    """A set of finding fingerprints previously accepted by a project."""

    fingerprints: frozenset[str]

    def contains(self, finding: Finding) -> bool:
        """Return whether a finding is represented by this baseline."""
        return bool(finding.fingerprint) and finding.fingerprint in self.fingerprints


def create_baseline(findings: list[Finding] | tuple[Finding, ...]) -> Baseline:
    """Create a baseline from findings with stable fingerprints."""
    return Baseline(
        frozenset(finding.fingerprint for finding in findings if finding.fingerprint)
    )


def save_baseline(path: Path, baseline: Baseline) -> None:
    """Write a deterministic JSON baseline."""
    payload = {"findings": sorted(baseline.fingerprints), "version": 1}
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_baseline(path: Path) -> Baseline:
    """Read and validate a JSON baseline."""
    try:
        payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BaselineError(f"{path}: invalid baseline: {error}") from error
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise BaselineError(f"{path}: unsupported baseline format")
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list) or not all(
        isinstance(fingerprint, str) and fingerprint for fingerprint in raw_findings
    ):
        raise BaselineError(f"{path}: findings must be a list of fingerprints")
    return Baseline(frozenset(raw_findings))


def filter_baselined(
    findings: list[Finding] | tuple[Finding, ...], baseline: Baseline
) -> list[Finding]:
    """Return only findings not already recorded in a baseline."""
    return [finding for finding in findings if not baseline.contains(finding)]
