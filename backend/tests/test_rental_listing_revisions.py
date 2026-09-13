import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from flyttsignal.domains.listings.revisions import (
    ListingRevisionCandidate,
    RentalListingRevisionFacts,
    RevisionChangeKind,
    RevisionProvenance,
    current_listing_revision,
    listing_revision_as_of,
    plan_listing_revision,
)


def revision_facts(**overrides: object) -> RentalListingRevisionFacts:
    values = {
        "listing_status": "ACTIVE",
        "available_from": date(2026, 10, 1),
        "application_deadline": date(2026, 9, 15),
        "new_construction": None,
        "categories": ("Senior", "Tillsvidarekontrakt"),
        "unit_identifier": "200062987276",
        "extra_normalized_facts": {"publisher": "Rikshem"},
    }
    values.update(overrides)
    return RentalListingRevisionFacts(**values)  # type: ignore[arg-type]


def test_revision_hash_is_derived_only_from_canonical_typed_facts() -> None:
    first = revision_facts(categories=("Senior", "Tillsvidarekontrakt"))
    second = revision_facts(categories=("Tillsvidarekontrakt", "Senior", "Senior"))

    assert first.fingerprint() == second.fingerprint()
    assert first.canonical_payload()["available_from"] == "2026-10-01"


def test_extra_facts_cannot_duplicate_canonical_columns() -> None:
    facts = revision_facts(extra_normalized_facts={"available_from": "2027-01-01"})

    with pytest.raises(ValueError, match="available_from"):
        facts.fingerprint()


def test_false_and_unknown_construction_have_different_revision_hashes() -> None:
    assert revision_facts(new_construction=False).fingerprint() != revision_facts(
        new_construction=None
    ).fingerprint()


def test_changed_advertised_date_creates_a_different_revision_identity() -> None:
    assert revision_facts().fingerprint() != revision_facts(
        available_from=date(2026, 10, 15)
    ).fingerprint()


def candidate(
    *,
    operation_key: str,
    valid_from: datetime,
    raw_payload: dict | None = None,
    content_hash: str | None = "a" * 64,
    provenance: RevisionProvenance = RevisionProvenance.DIRECT,
    facts: RentalListingRevisionFacts | None = None,
) -> ListingRevisionCandidate:
    direct = provenance == RevisionProvenance.DIRECT
    return ListingRevisionCandidate(
        operation_key=operation_key,
        change_kind=RevisionChangeKind.CONTENT_OBSERVED,
        provenance_kind=provenance,
        valid_from=valid_from,
        source_run_id=uuid.UUID(int=10) if direct else None,
        raw_item_id=uuid.UUID(int=20) if direct else None,
        content_hash=content_hash,
        raw_payload=raw_payload if raw_payload is not None else {"moveInDate": "2026-10-01"},
        facts=facts or revision_facts(),
    )


def test_identical_observation_does_not_create_an_extra_content_revision() -> None:
    observed_at = datetime(2026, 9, 10, 12, tzinfo=UTC)
    first = plan_listing_revision(
        None,
        candidate(operation_key="run:first", valid_from=observed_at),
    )
    assert first is not None

    repeated = plan_listing_revision(
        first,
        candidate(operation_key="run:second", valid_from=observed_at + timedelta(hours=1)),
    )

    assert repeated is None


def test_revision_owns_a_historical_copy_of_its_raw_payload() -> None:
    raw_payload = {"moveInDate": "2026-10-01", "categories": ["Senior"]}
    planned = plan_listing_revision(
        None,
        candidate(
            operation_key="run:first",
            valid_from=datetime(2026, 9, 10, 12, tzinfo=UTC),
            raw_payload=raw_payload,
        ),
    )
    assert planned is not None

    raw_payload["moveInDate"] = "2026-11-01"
    raw_payload["categories"].append("Changed later")

    assert planned.raw_payload == {
        "moveInDate": "2026-10-01",
        "categories": ["Senior"],
    }


def test_current_and_as_of_resolution_choose_the_correct_revision() -> None:
    cutover = datetime(2026, 9, 10, 20, tzinfo=UTC)
    baseline = plan_listing_revision(
        None,
        candidate(
            operation_key="cutover:baseline",
            valid_from=cutover,
            provenance=RevisionProvenance.RECONSTRUCTED,
            content_hash="b" * 64,
        ),
    )
    assert baseline is not None
    changed = plan_listing_revision(
        baseline,
        candidate(
            operation_key="run:changed",
            valid_from=cutover + timedelta(days=2),
            facts=revision_facts(available_from=date(2026, 10, 15)),
            content_hash="c" * 64,
        ),
    )
    assert changed is not None
    revisions = (changed, baseline)

    assert listing_revision_as_of(revisions, cutover - timedelta(seconds=1)) is None
    assert listing_revision_as_of(revisions, cutover) == baseline
    assert listing_revision_as_of(revisions, cutover + timedelta(days=1)) == baseline
    assert listing_revision_as_of(revisions, cutover + timedelta(days=3)) == changed
    assert current_listing_revision(revisions) == changed


def test_reused_operation_key_with_different_facts_is_rejected() -> None:
    observed_at = datetime(2026, 9, 10, 12, tzinfo=UTC)
    first = plan_listing_revision(
        None,
        candidate(operation_key="run:one", valid_from=observed_at),
    )
    assert first is not None

    with pytest.raises(ValueError, match="operation key"):
        plan_listing_revision(
            first,
            candidate(
                operation_key="run:one",
                valid_from=observed_at,
                facts=revision_facts(available_from=date(2027, 1, 1)),
            ),
        )


def test_direct_revision_requires_complete_provenance() -> None:
    with pytest.raises(ValueError, match="source run"):
        plan_listing_revision(
            None,
            ListingRevisionCandidate(
                operation_key="invalid",
                change_kind=RevisionChangeKind.CONTENT_OBSERVED,
                provenance_kind=RevisionProvenance.DIRECT,
                valid_from=datetime(2026, 9, 10, 12, tzinfo=UTC),
                source_run_id=None,
                raw_item_id=None,
                content_hash=None,
                raw_payload=None,
                facts=revision_facts(),
            ),
        )
