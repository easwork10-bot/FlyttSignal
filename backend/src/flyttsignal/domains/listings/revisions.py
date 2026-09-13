import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

NORMALIZATION_REVISION = "rental-listing-canonical-2026-09"
CANONICAL_FIELDS = frozenset(
    {
        "listing_status",
        "available_from",
        "application_deadline",
        "new_construction",
        "categories",
        "unit_identifier",
    }
)


class RevisionChangeKind(StrEnum):
    CONTENT_OBSERVED = "CONTENT_OBSERVED"
    LISTING_REMOVED = "LISTING_REMOVED"
    LISTING_RELISTED = "LISTING_RELISTED"


class RevisionProvenance(StrEnum):
    DIRECT = "DIRECT"
    RECONSTRUCTED = "RECONSTRUCTED"


@dataclass(frozen=True)
class RentalListingRevisionFacts:
    listing_status: str
    available_from: date | None
    application_deadline: date | None
    new_construction: bool | None
    categories: tuple[str, ...]
    unit_identifier: str | None
    extra_normalized_facts: dict[str, Any] = field(default_factory=dict)
    normalization_revision: str = NORMALIZATION_REVISION

    def canonical_payload(self) -> dict[str, Any]:
        duplicated = CANONICAL_FIELDS.intersection(self.extra_normalized_facts)
        if duplicated:
            names = ", ".join(sorted(duplicated))
            raise ValueError(f"extra facts duplicate canonical fields: {names}")
        return {
            "normalization_revision": self.normalization_revision,
            "listing_status": self.listing_status,
            "available_from": self.available_from.isoformat() if self.available_from else None,
            "application_deadline": (
                self.application_deadline.isoformat() if self.application_deadline else None
            ),
            "new_construction": self.new_construction,
            "categories": sorted(set(self.categories)),
            "unit_identifier": self.unit_identifier,
            "extra_normalized_facts": self.extra_normalized_facts,
        }

    def fingerprint(self) -> str:
        serialized = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(serialized.encode()).hexdigest()


@dataclass(frozen=True)
class ListingRevisionState:
    id: uuid.UUID
    revision_number: int
    operation_key: str
    change_kind: RevisionChangeKind
    provenance_kind: RevisionProvenance
    valid_from: datetime
    source_run_id: uuid.UUID | None
    raw_item_id: uuid.UUID | None
    content_hash: str | None
    raw_payload: dict[str, Any] | None
    facts: RentalListingRevisionFacts


@dataclass(frozen=True)
class ListingRevisionCandidate:
    operation_key: str
    change_kind: RevisionChangeKind
    provenance_kind: RevisionProvenance
    valid_from: datetime
    source_run_id: uuid.UUID | None
    raw_item_id: uuid.UUID | None
    content_hash: str | None
    raw_payload: dict[str, Any] | None
    facts: RentalListingRevisionFacts


def plan_listing_revision(
    latest: ListingRevisionState | None,
    candidate: ListingRevisionCandidate,
) -> ListingRevisionState | None:
    """Plan one immutable revision, returning None for a repeated observation."""

    _require_aware(candidate.valid_from)
    if candidate.provenance_kind == RevisionProvenance.DIRECT and (
        candidate.source_run_id is None
        or candidate.raw_item_id is None
        or candidate.content_hash is None
        or candidate.raw_payload is None
    ):
        raise ValueError(
            "direct listing revisions require source run, raw item, payload, and content hash"
        )
    if latest and latest.operation_key == candidate.operation_key:
        if _same_revision(latest, candidate):
            return None
        raise ValueError("revision operation key was already used for different facts")
    if (
        candidate.change_kind == RevisionChangeKind.CONTENT_OBSERVED
        and latest is not None
        and latest.content_hash == candidate.content_hash
        and latest.facts.fingerprint() == candidate.facts.fingerprint()
    ):
        return None

    return ListingRevisionState(
        id=uuid.uuid4(),
        revision_number=(latest.revision_number + 1) if latest else 1,
        operation_key=candidate.operation_key,
        change_kind=candidate.change_kind,
        provenance_kind=candidate.provenance_kind,
        valid_from=candidate.valid_from,
        source_run_id=candidate.source_run_id,
        raw_item_id=candidate.raw_item_id,
        content_hash=candidate.content_hash,
        raw_payload=deepcopy(candidate.raw_payload),
        facts=candidate.facts,
    )


def current_listing_revision(
    revisions: tuple[ListingRevisionState, ...],
) -> ListingRevisionState | None:
    return _latest(revisions)


def listing_revision_as_of(
    revisions: tuple[ListingRevisionState, ...], as_of: datetime
) -> ListingRevisionState | None:
    _require_aware(as_of)
    return _latest(tuple(revision for revision in revisions if revision.valid_from <= as_of))


def _latest(revisions: tuple[ListingRevisionState, ...]) -> ListingRevisionState | None:
    return max(
        revisions,
        key=lambda revision: (revision.valid_from, revision.revision_number, str(revision.id)),
        default=None,
    )


def _same_revision(
    existing: ListingRevisionState, candidate: ListingRevisionCandidate
) -> bool:
    return (
        existing.change_kind == candidate.change_kind
        and existing.provenance_kind == candidate.provenance_kind
        and existing.valid_from == candidate.valid_from
        and existing.source_run_id == candidate.source_run_id
        and existing.raw_item_id == candidate.raw_item_id
        and existing.content_hash == candidate.content_hash
        and existing.facts.fingerprint() == candidate.facts.fingerprint()
        and existing.raw_payload == candidate.raw_payload
    )


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("listing revision timestamps must be timezone-aware")
