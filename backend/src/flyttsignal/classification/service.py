from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import RentalListing, RentalListingClassification
from flyttsignal.domains.listings import classification as listing_classification


def sync_listing_classifications(
    session: Session,
    listing: RentalListing,
    *,
    new_construction: bool | None,
    categories: list[str],
) -> tuple[listing_classification.Classification, ...]:
    desired = listing_classification.classify_listing(
        new_construction=new_construction,
        categories=categories,
    )
    existing = {
        row.tag: row
        for row in session.scalars(
            select(RentalListingClassification).where(
                RentalListingClassification.listing_id == listing.id,
                RentalListingClassification.rule_version
                == listing_classification.CLASSIFICATION_RULE_VERSION,
            )
        )
    }
    desired_tags = {item.tag for item in desired}
    for tag, row in existing.items():
        if tag not in desired_tags:
            session.delete(row)
    for item in desired:
        row = existing.get(item.tag)
        if row is None:
            row = RentalListingClassification(
                listing_id=listing.id,
                tag=item.tag,
                rule_version=item.rule_version,
            )
            session.add(row)
        row.confidence = item.confidence
        row.reason = item.reason
        row.evidence = item.evidence
    return desired
