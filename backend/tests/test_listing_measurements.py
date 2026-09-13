import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from flyttsignal.db.models import ListingMeasurement, RentalListing
from flyttsignal.domains.listings.measurements import (
    LEAD_TIME_RULE_VERSION,
    measure_lead_time,
)
from flyttsignal.measurements.service import sync_lead_time_measurement


def test_lead_time_uses_stockholm_calendar_date() -> None:
    measured = measure_lead_time(
        first_seen_at=datetime(2026, 8, 29, 22, 30, tzinfo=UTC),
        available_from=date(2026, 8, 31),
    )

    assert measured.status == "MEASURED"
    assert measured.value == Decimal("1")
    assert measured.inputs["first_seen_local_date"] == "2026-08-30"
    assert measured.rule_version == LEAD_TIME_RULE_VERSION


def test_missing_available_date_is_a_persistable_quality_fact() -> None:
    measured = measure_lead_time(
        first_seen_at=datetime(2026, 8, 30, tzinfo=UTC),
        available_from=None,
    )

    assert measured.status == "MISSING_INPUT"
    assert measured.value is None
    assert measured.inputs["missing"] == ["available_from"]


def test_negative_lead_time_is_not_clamped() -> None:
    measured = measure_lead_time(
        first_seen_at=datetime(2026, 8, 30, 10, tzinfo=UTC),
        available_from=date(2026, 8, 29),
    )

    assert measured.value == Decimal("-1")
    assert measured.inputs["late_observation"] is True


def test_naive_first_seen_timestamp_fails_closed() -> None:
    measured = measure_lead_time(
        first_seen_at=datetime(2026, 8, 30, 10),
        available_from=date(2026, 9, 1),
    )

    assert measured.status == "INVALID_INPUT"
    assert measured.value is None


class StubSession:
    def __init__(self):
        self.row = None
        self.added = 0

    def scalar(self, _statement):
        return self.row

    def add(self, row):
        self.row = row
        self.added += 1


def test_measurement_sync_is_idempotent() -> None:
    session = StubSession()
    listing = RentalListing(
        id=uuid.uuid4(),
        first_seen_at=datetime(2026, 8, 30, tzinfo=UTC),
        available_from=date(2026, 9, 30),
    )

    sync_lead_time_measurement(session, listing)
    sync_lead_time_measurement(session, listing)

    assert session.added == 1
    assert session.row.value == Decimal("31")
    assert session.row.status == "MEASURED"


def test_listing_measurement_schema_is_versioned_and_auditable() -> None:
    columns = ListingMeasurement.__table__.columns
    assert {
        "listing_id",
        "metric",
        "value",
        "unit",
        "status",
        "rule_version",
        "inputs",
    } <= set(columns.keys())
