from flyttsignal.api.mappers.properties import property_out
from flyttsignal.api.schemas.rental_listings import RentalListingOut
from flyttsignal.db.models import RentalListing


def rental_listing_out(listing: RentalListing) -> RentalListingOut:
    return RentalListingOut(
        id=listing.id,
        source_item_id=listing.source_item_id,
        publisher=listing.source.name,
        upstream_provider_key=listing.upstream_provider_key,
        upstream_provider_name=listing.upstream_provider_name,
        unit_identifier=listing.unit_identifier,
        rooms=listing.rooms,
        area_m2=listing.area_m2,
        new_construction=listing.new_construction,
        canonical_url=listing.canonical_url,
        monthly_rent=listing.monthly_rent,
        application_deadline=listing.application_deadline,
        available_from=listing.available_from,
        categories=listing.categories,
        data_mode=listing.data_mode,
        attribution=listing.attribution,
        status=listing.status,
        first_seen_at=listing.first_seen_at,
        last_seen_at=listing.last_seen_at,
        removed_at=listing.removed_at,
        property=property_out(listing.property),
    )
