import uuid
from decimal import Decimal

from flyttsignal.classification.service import sync_listing_classifications
from flyttsignal.db.models import RentalListing, RentalListingClassification
from flyttsignal.domains.listings.classification import (
    CLASSIFICATION_RULE_VERSION,
    classify_listing,
    resolve_construction_state,
)


def test_missing_optional_enrichment_retains_prior_construction_fact() -> None:
    assert resolve_construction_state(observed=None, previous=True) is True
    assert resolve_construction_state(observed=None, previous=False) is False
    assert resolve_construction_state(observed=None, previous=None) is None
    assert resolve_construction_state(observed=False, previous=True) is False


def test_complete_tristate_observation_repairs_legacy_false_but_retains_positive() -> None:
    assert (
        resolve_construction_state(
            observed=None,
            previous=False,
            observation_complete=True,
        )
        is None
    )
    assert (
        resolve_construction_state(
            observed=None,
            previous=True,
            observation_complete=True,
        )
        is True
    )


def test_explicit_evidence_produces_multiple_auditable_tags() -> None:
    found = classify_listing(
        new_construction=True,
        categories=[
            "hyresrätt",
            "marknadsplats",
            "Studentboende",
            "Korttidskontrakt",
        ],
    )

    assert {item.tag for item in found} == {
        "NEW_CONSTRUCTION",
        "STUDENT_HOUSING",
        "SHORT_TERM",
    }
    assert all(item.confidence == Decimal("1.000") for item in found)
    assert all(item.rule_version == CLASSIFICATION_RULE_VERSION for item in found)
    assert all(item.evidence for item in found)


def test_generic_channel_categories_fail_closed_to_unknown() -> None:
    found = classify_listing(
        new_construction=False,
        categories=["hyresrätt", "direktkanal", "publik-sökning", "projektbostad"],
    )

    assert len(found) == 1
    assert found[0].tag == "UNKNOWN"
    assert found[0].confidence == Decimal("0.000")
    assert found[0].reason == "no_explicit_classification_evidence"


def test_public_category_matching_is_whitespace_and_case_stable() -> None:
    found = classify_listing(
        new_construction=False,
        categories=["  TILLSVIDAREKONTRAKT ", " Lägenhet"],
    )

    assert {item.tag for item in found} == {"PERMANENT_CONTRACT", "APARTMENT"}


class StubSession:
    def __init__(self):
        self.rows: list[RentalListingClassification] = []

    def scalars(self, _statement):
        return iter(self.rows.copy())

    def add(self, row):
        self.rows.append(row)

    def delete(self, row):
        self.rows.remove(row)


def test_sync_is_idempotent_and_removes_stale_v1_tags() -> None:
    session = StubSession()
    listing = RentalListing(id=uuid.uuid4())

    sync_listing_classifications(
        session,
        listing,
        new_construction=False,
        categories=["Studentboende"],
    )
    sync_listing_classifications(
        session,
        listing,
        new_construction=False,
        categories=["Studentboende"],
    )
    assert [row.tag for row in session.rows] == ["STUDENT_HOUSING"]

    sync_listing_classifications(
        session,
        listing,
        new_construction=False,
        categories=["direktkanal"],
    )
    assert [row.tag for row in session.rows] == ["UNKNOWN"]


def test_classification_schema_keeps_evidence_and_rule_version() -> None:
    columns = RentalListingClassification.__table__.columns
    assert {
        "listing_id",
        "tag",
        "confidence",
        "reason",
        "evidence",
        "rule_version",
    } <= set(columns.keys())
