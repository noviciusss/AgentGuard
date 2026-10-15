"""Deterministic, privacy-safe helpers for public risk badges.

The badge contract deliberately accepts only aggregate severity counts.  This
keeps source locations, finding messages, and other scan details outside the
public reporting boundary even when a caller has a full scan object available.
"""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Literal


class RiskLevel(str, Enum):
    """Risk levels exposed by a public badge."""

    PASSING = "passing"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BadgeStatus(str, Enum):
    """Availability state of the data represented by a badge."""

    AVAILABLE = "available"
    MISSING = "missing"
    STALE = "stale"
    PRIVATE = "private"
    UNAVAILABLE = "unavailable"


class BadgeVisibility(str, Enum):
    """Visibility requested by the repository owner."""

    PUBLIC = "public"
    PRIVATE = "private"


@dataclass(frozen=True, slots=True)
class FindingCounts:
    """Aggregate counts grouped by AgentGuard finding severity.

    Counts are intentionally limited to the three severities in the findings
    contract.  They contain no finding identity or source information.
    """

    errors: int = 0
    warnings: int = 0
    infos: int = 0

    def __post_init__(self) -> None:
        """Reject negative or non-integer counts at the boundary."""
        for name, value in (
            ("errors", self.errors),
            ("warnings", self.warnings),
            ("infos", self.infos),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")

    @property
    def total(self) -> int:
        """Return the total number of findings represented by the counts."""
        return self.errors + self.warnings + self.infos

    @classmethod
    def from_severity_counts(cls, counts: Mapping[str, int]) -> FindingCounts:
        """Create counts from a severity-to-count mapping.

        Missing severities are treated as zero.  Unknown severity names are
        rejected rather than silently omitted from the risk calculation.
        Severity names are case-insensitive and surrounding whitespace is
        ignored so equivalent inputs produce the same result.
        """
        normalized: dict[str, int] = {}
        for severity, count in counts.items():
            key = severity.strip().lower()
            if key not in {"error", "warning", "info"}:
                raise ValueError(f"unsupported severity: {severity!r}")
            if key in normalized:
                raise ValueError(f"duplicate severity: {severity!r}")
            normalized[key] = count
        return cls(
            errors=normalized.get("error", 0),
            warnings=normalized.get("warning", 0),
            infos=normalized.get("info", 0),
        )

    def as_dict(self) -> dict[str, int]:
        """Return the stable public names for the aggregate counts."""
        return {
            "error": self.errors,
            "warning": self.warnings,
            "info": self.infos,
        }


def calculate_risk_level(counts: FindingCounts) -> RiskLevel:
    """Calculate a deterministic risk level from aggregate severity counts.

    The thresholds are deliberately simple and severity-first:

    * any error, or at least ten warnings, is ``high``;
    * one to nine warnings, or at least ten informational findings, is
      ``medium``;
    * one to nine informational findings is ``low``;
    * no findings is ``passing``.

    An error always outranks lower-severity counts.  The function consumes only
    validated aggregate counts, so it cannot disclose source-level data.
    """
    if counts.errors > 0 or counts.warnings >= 10:
        return RiskLevel.HIGH
    if counts.warnings > 0 or counts.infos >= 10:
        return RiskLevel.MEDIUM
    if counts.infos > 0:
        return RiskLevel.LOW
    return RiskLevel.PASSING


BadgeFormat = Literal["svg", "json"]
BadgeMediaType = Literal["image/svg+xml", "application/json"]


_DEFAULT_MAX_AGE = timedelta(days=7)
_CACHE_CONTROL: dict[BadgeStatus, str] = {
    BadgeStatus.AVAILABLE: "public, max-age=300, must-revalidate",
    BadgeStatus.STALE: "public, max-age=60, must-revalidate",
    BadgeStatus.MISSING: "public, max-age=60, must-revalidate",
    BadgeStatus.UNAVAILABLE: "public, max-age=30, must-revalidate",
    BadgeStatus.PRIVATE: "private, no-store",
}
_COLORS: dict[RiskLevel | BadgeStatus, str] = {
    RiskLevel.PASSING: "#4c1",
    RiskLevel.LOW: "#97ca00",
    RiskLevel.MEDIUM: "#dfb317",
    RiskLevel.HIGH: "#e05d44",
    BadgeStatus.MISSING: "#9f9f9f",
    BadgeStatus.STALE: "#dfb317",
    BadgeStatus.PRIVATE: "#9f9f9f",
    BadgeStatus.UNAVAILABLE: "#9f9f9f",
}


@dataclass(frozen=True, slots=True)
class BadgeResponse:
    """Aggregate-only badge response with deterministic render helpers."""

    status: BadgeStatus
    risk_level: RiskLevel | None
    counts: FindingCounts | None
    label: str
    message: str

    @property
    def state(self) -> BadgeStatus:
        """Alias for callers that model availability as a state."""
        return self.status

    @property
    def level(self) -> RiskLevel | None:
        """Alias for the calculated risk level."""
        return self.risk_level

    @property
    def cache_control(self) -> str:
        """Return cache policy appropriate for this response state."""
        return _CACHE_CONTROL[self.status]

    def as_dict(self) -> dict[str, object]:
        """Return the stable, source-free JSON representation."""
        return {
            "schema_version": 1,
            "status": self.status.value,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "label": self.label,
            "message": self.message,
            "counts": self.counts.as_dict() if self.counts else None,
        }

    def to_json(self) -> str:
        """Serialize the response with stable key order and separators."""
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

    @property
    def etag(self) -> str:
        """Return a content-derived, quoted strong ETag."""
        digest = hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
        return f'"{digest}"'

    def headers(
        self, *, media_type: BadgeMediaType = "image/svg+xml"
    ) -> dict[str, str]:
        """Return deterministic cache and content headers for the badge."""
        return {
            "Cache-Control": self.cache_control,
            "Content-Type": media_type,
            "ETag": self.etag,
        }

    def render_svg(self) -> str:
        """Render a compact SVG containing only generic aggregate status text."""
        color_key: RiskLevel | BadgeStatus = (
            self.risk_level if self.risk_level is not None else self.status
        )
        color = _COLORS[color_key]
        escaped_label = html.escape(self.label, quote=True)
        escaped_message = html.escape(self.message, quote=True)
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="180" height="20" '
            f'role="img" aria-label="{escaped_message}">'
            f"<title>{escaped_message}</title>"
            f'<rect width="180" height="20" fill="{color}"/>'
            '<text x="90" y="14" fill="#fff" text-anchor="middle" '
            'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
            f"{escaped_label}</text></svg>"
        )

    def render(self, format: BadgeFormat = "svg") -> str:
        """Render the response as SVG or deterministic JSON."""
        if format == "svg":
            return self.render_svg()
        if format == "json":
            return self.to_json()
        raise ValueError(f"unsupported badge format: {format!r}")


def _utc(value: datetime) -> datetime:
    """Normalize an input timestamp for deterministic age comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _content_for(
    status: BadgeStatus, counts: FindingCounts | None
) -> tuple[RiskLevel | None, FindingCounts | None, str, str]:
    """Build generic display content without carrying scan details through."""
    if status in {BadgeStatus.AVAILABLE, BadgeStatus.STALE}:
        if counts is None:
            raise ValueError("available badge states require counts")
        risk_level = calculate_risk_level(counts)
        suffix = " (stale)" if status is BadgeStatus.STALE else ""
        return (
            risk_level,
            counts,
            f"risk: {risk_level.value}{suffix}",
            "Risk level is based on stale scan data."
            if status is BadgeStatus.STALE
            else "Risk level based on the latest scan.",
        )
    messages = {
        BadgeStatus.MISSING: ("risk: no data", "No scan data available."),
        BadgeStatus.PRIVATE: ("risk: private", "Repository is private."),
        BadgeStatus.UNAVAILABLE: (
            "risk: unavailable",
            "Risk data is temporarily unavailable.",
        ),
    }
    label, message = messages[status]
    return None, None, label, message


def build_badge_response(
    counts: FindingCounts | None,
    *,
    now: datetime,
    updated_at: datetime | None = None,
    max_age: timedelta = _DEFAULT_MAX_AGE,
    visibility: BadgeVisibility = BadgeVisibility.PUBLIC,
    unavailable: bool = False,
) -> BadgeResponse:
    """Build a cache-safe response for aggregate repository risk data.

    ``now`` is required so callers can make the freshness decision explicit
    and tests can reproduce the exact same response.  A private repository
    never returns counts or a risk level.  A missing scan is distinct from an
    unavailable service; counts without an observation timestamp are treated
    as unavailable because their freshness cannot be established safely.
    """
    if max_age < timedelta(0):
        raise ValueError("max_age must be non-negative")

    status: BadgeStatus
    if visibility is BadgeVisibility.PRIVATE:
        status = BadgeStatus.PRIVATE
    elif unavailable:
        status = BadgeStatus.UNAVAILABLE
    elif counts is None:
        status = BadgeStatus.MISSING
    elif updated_at is None:
        status = BadgeStatus.UNAVAILABLE
    else:
        age = _utc(now) - _utc(updated_at)
        status = BadgeStatus.STALE if age > max_age else BadgeStatus.AVAILABLE

    response_counts = (
        counts if status in {BadgeStatus.AVAILABLE, BadgeStatus.STALE} else None
    )
    risk_level, response_counts, label, message = _content_for(status, response_counts)
    return BadgeResponse(
        status=status,
        risk_level=risk_level,
        counts=response_counts,
        label=label,
        message=message,
    )


def render_badge(response: BadgeResponse, format: BadgeFormat = "svg") -> str:
    """Render a previously built badge response in the selected format."""
    return response.render(format)
