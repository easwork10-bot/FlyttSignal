"""Preview or persist classification-v1 for existing live rental listings."""

import argparse
import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from flyttsignal.classification.service import (
    classify_listing,
    sync_listing_classifications,
)
from flyttsignal.db.models import RentalListing
from flyttsignal.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    counts: Counter[str] = Counter()

    with SessionLocal() as session:
        listings = list(
            session.scalars(
                select(RentalListing)
                .options(selectinload(RentalListing.raw_item))
                .where(RentalListing.data_mode == "live")
                .order_by(RentalListing.id)
            )
        )
        for listing in listings:
            new_construction = bool(listing.raw_item.raw_payload.get("new_construction") is True)
            classifications = classify_listing(
                new_construction=new_construction,
                categories=listing.categories,
            )
            counts.update(item.tag for item in classifications)
            if args.apply:
                sync_listing_classifications(
                    session,
                    listing,
                    new_construction=new_construction,
                    categories=listing.categories,
                )
        if args.apply:
            session.commit()

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "listings": len(listings),
                "classification_rows": sum(counts.values()),
                "tags": dict(sorted(counts.items())),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
