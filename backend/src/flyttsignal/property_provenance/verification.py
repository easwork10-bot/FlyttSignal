"""Temporal verification rules for property-provenance projections."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from flyttsignal.domains.signals.evidence import EvidenceEdge, valid_as_of


class VerificationMode(StrEnum):
    AS_OF = "as-of"
    CURRENT = "current"


class VerificationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProjectionCheck:
    status: VerificationStatus
    reason: str


HISTORICAL_VALUE_NOT_CAPTURED = object()


def evidence_applies(evidence: EvidenceEdge, *, mode: VerificationMode, as_of: datetime) -> bool:
    if mode is VerificationMode.AS_OF:
        return valid_as_of(evidence, as_of)
    return evidence.superseded_at is None


def verify_projection(
    *,
    mode: VerificationMode,
    current_expected: Any,
    current_actual: Any,
    historical_expected: Any = HISTORICAL_VALUE_NOT_CAPTURED,
    historical_actual: Any = HISTORICAL_VALUE_NOT_CAPTURED,
) -> ProjectionCheck:
    if mode is VerificationMode.CURRENT:
        if current_actual == current_expected:
            return ProjectionCheck(VerificationStatus.PASS, "current_projection_matches")
        return ProjectionCheck(VerificationStatus.FAIL, "current_projection_mismatch")
    if (
        historical_expected is HISTORICAL_VALUE_NOT_CAPTURED
        or historical_actual is HISTORICAL_VALUE_NOT_CAPTURED
    ):
        return ProjectionCheck(
            VerificationStatus.UNKNOWN,
            "historical_property_identity_not_captured",
        )
    if historical_actual == historical_expected:
        return ProjectionCheck(VerificationStatus.PASS, "historical_projection_matches")
    return ProjectionCheck(VerificationStatus.FAIL, "historical_projection_mismatch")
