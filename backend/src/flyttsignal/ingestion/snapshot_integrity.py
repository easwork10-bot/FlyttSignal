from dataclasses import dataclass
from enum import StrEnum

from flyttsignal.ingestion.contracts import (
    DEFAULT_COMPLETENESS_RULE_VERSION,
    SnapshotEvidence,
)

COMPLETENESS_RULE_VERSION = DEFAULT_COMPLETENESS_RULE_VERSION


class SnapshotStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class SnapshotAssessment:
    status: SnapshotStatus
    reasons: tuple[str, ...]
    rule_version: str = DEFAULT_COMPLETENESS_RULE_VERSION


def assess_snapshot(evidence: SnapshotEvidence) -> SnapshotAssessment:
    """Apply the conservative, versioned M3.1 completeness rule."""

    reasons = list(evidence.reasons)
    blockers: list[str] = []
    if evidence.requests_failed not in (None, 0):
        blockers.append("one_or_more_requests_failed")
    if (
        evidence.requests_attempted is not None
        and evidence.requests_succeeded is not None
        and evidence.requests_attempted != evidence.requests_succeeded
    ):
        blockers.append("request_count_mismatch")
    if evidence.pagination_complete is False:
        blockers.append("pagination_incomplete")
    if (
        evidence.pages_expected is not None
        and evidence.pages_received is not None
        and evidence.pages_expected != evidence.pages_received
    ):
        blockers.append("page_count_mismatch")
    if (
        evidence.items_reported is not None
        and evidence.items_received is not None
        and evidence.items_reported != evidence.items_received
    ):
        blockers.append("item_count_mismatch")
    if evidence.hit_result_limit is True:
        blockers.append("result_limit_reached")
    if evidence.inventory_scope_complete is False:
        blockers.append("inventory_scope_known_incomplete")
    if blockers:
        return SnapshotAssessment(
            SnapshotStatus.INCOMPLETE,
            tuple(dict.fromkeys(reasons + blockers)),
            evidence.rule_version,
        )

    complete_proof = (
        evidence.inventory_scope_complete is True
        and evidence.requests_attempted is not None
        and evidence.requests_attempted > 0
        and evidence.requests_succeeded == evidence.requests_attempted
        and evidence.requests_failed == 0
        and evidence.pagination_complete is True
        and evidence.hit_result_limit is False
        and evidence.items_reported is not None
        and evidence.items_received == evidence.items_reported
        and (evidence.pages_expected is None or evidence.pages_received == evidence.pages_expected)
    )
    if complete_proof:
        return SnapshotAssessment(
            SnapshotStatus.COMPLETE,
            tuple(dict.fromkeys(reasons)),
            evidence.rule_version,
        )
    reasons.append("complete_inventory_not_proven")
    return SnapshotAssessment(
        SnapshotStatus.UNKNOWN,
        tuple(dict.fromkeys(reasons)),
        evidence.rule_version,
    )
