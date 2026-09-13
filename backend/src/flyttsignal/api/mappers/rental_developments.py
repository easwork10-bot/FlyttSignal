from flyttsignal.api.schemas.rental_developments import RentalProjectOut
from flyttsignal.db.models import RentalProject


def rental_project_out(project: RentalProject, imported_count: int) -> RentalProjectOut:
    return RentalProjectOut(
        id=project.id,
        source_item_id=project.source_item_id,
        name=project.name,
        canonical_url=project.canonical_url,
        upstream_provider_key=project.upstream_provider_key,
        upstream_provider_name=project.upstream_provider_name,
        address=project.address,
        city=project.city,
        planned_unit_count=project.planned_unit_count,
        active_listing_count=project.active_listing_count,
        imported_listing_count=imported_count,
        rent_min=project.rent_min,
        rent_max=project.rent_max,
        rooms_min=project.rooms_min,
        rooms_max=project.rooms_max,
        area_min=project.area_min,
        area_max=project.area_max,
        available_from=project.available_from,
        status=project.status,
        data_mode=project.data_mode,
        attribution=project.attribution,
        last_seen_at=project.last_seen_at,
    )
