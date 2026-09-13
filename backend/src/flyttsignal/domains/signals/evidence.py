from datetime import datetime
from typing import Protocol
from uuid import UUID


class EvidenceEdge(Protocol):
    event_id: UUID
    valid_from: datetime
    superseded_at: datetime | None
    superseded_by_event_id: UUID | None
    supersession_reason: str | None


def supersede_evidence(
    evidence: EvidenceEdge,
    *,
    replacement_event_id: UUID,
    superseded_at: datetime,
    reason: str,
) -> bool:
    """Close one evidence edge while retaining it as immutable audit history."""

    normalized_reason = " ".join(reason.split())
    if not normalized_reason:
        raise ValueError("evidence supersession requires a reason")
    if superseded_at.tzinfo is None or superseded_at.utcoffset() is None:
        raise ValueError("evidence supersession requires a timezone-aware timestamp")
    if evidence.event_id == replacement_event_id:
        raise ValueError("replacement event must differ from the superseded event")
    if superseded_at < evidence.valid_from:
        raise ValueError("evidence cannot be superseded before it became valid")

    if evidence.superseded_at is not None:
        if (
            evidence.superseded_by_event_id == replacement_event_id
            and evidence.superseded_at == superseded_at
            and evidence.supersession_reason == normalized_reason
        ):
            return False
        raise ValueError("evidence was already superseded by a different decision")

    evidence.superseded_at = superseded_at
    evidence.superseded_by_event_id = replacement_event_id
    evidence.supersession_reason = normalized_reason
    return True


def valid_as_of(evidence: EvidenceEdge, as_of: datetime) -> bool:
    """Return whether an evidence edge was valid at an exact historical instant."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("evidence as-of evaluation requires a timezone-aware timestamp")
    return evidence.valid_from <= as_of and (
        evidence.superseded_at is None or as_of < evidence.superseded_at
    )
