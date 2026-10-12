"""Stable finding fingerprint helpers."""

import hashlib
from pathlib import Path


def normalize_snippet(snippet: str) -> str:
    """Collapse source whitespace for line-number-independent hashing."""
    return " ".join(snippet.split())


def fingerprint(rule_id: str, relative_file: Path, snippet: str) -> str:
    """Create the 16-character fingerprint specified for a finding.

    Line and column numbers are intentionally not included. Moving an
    otherwise identical finding within a file therefore keeps its identity.
    """
    normalized_snippet = normalize_snippet(snippet)
    payload = f"{rule_id}{relative_file.as_posix()}{normalized_snippet}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
