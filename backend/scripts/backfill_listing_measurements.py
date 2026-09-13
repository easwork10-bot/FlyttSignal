"""Preview or persist lead-time-v1 for existing live rental listings."""

import argparse
import json
from collections import Counter

from sqlalchemy import select

from flyttsignal.db.models import RentalListing
from flyttsignal.db.session import SessionLocal
from flyttsignal.measurements.service import measure_lead_time, sync_lead_time_measurement


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    statuses: Counter[str] = Counter()
    values = []

    with SessionLocal() as session:
        listings = list(
            session.scalars(
                select(RentalListing)
                .where(RentalListing.data_mode == "live")
                .order_by(RentalListing.id)
            )
        )
        for listing in listings:
            measurement = measure_lead_time(
                first_seen_at=listing.first_seen_at,
                available_from=listing.available_from,
            )
            statuses[measurement.status] += 1
            if measurement.value is not None:
                values.append(measurement.value)
            if args.apply:
                sync_lead_time_measurement(session, listing)
        if args.apply:
            session.commit()

    ordered = sorted(values)
    middle = len(ordered) // 2
    median = (
        None
        if not ordered
        else ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )
    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "listings": len(listings),
                "statuses": dict(sorted(statuses.items())),
                "min_days": str(min(ordered)) if ordered else None,
                "median_days": str(median) if median is not None else None,
                "max_days": str(max(ordered)) if ordered else None,
            }
        )
    )


if __name__ == "__main__":
    main()
