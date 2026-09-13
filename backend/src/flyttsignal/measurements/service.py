from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import ListingMeasurement, RentalListing
from flyttsignal.domains.listings import measurements as listing_measurements


def sync_lead_time_measurement(
    session: Session, listing: RentalListing
) -> listing_measurements.Measurement:
    measured = listing_measurements.measure_lead_time(
        first_seen_at=listing.first_seen_at,
        available_from=listing.available_from,
    )
    row = session.scalar(
        select(ListingMeasurement).where(
            ListingMeasurement.listing_id == listing.id,
            ListingMeasurement.metric == measured.metric,
            ListingMeasurement.rule_version == measured.rule_version,
        )
    )
    if row is None:
        row = ListingMeasurement(
            listing_id=listing.id,
            metric=measured.metric,
            rule_version=measured.rule_version,
        )
        session.add(row)
    row.value = measured.value
    row.unit = measured.unit
    row.status = measured.status
    row.inputs = measured.inputs
    return measured
