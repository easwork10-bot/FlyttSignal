from flyttsignal.api.schemas.properties import (
    AddressEnrichmentOut,
    PropertyOut,
    RegisterUnitReferenceOut,
)
from flyttsignal.db.models import Property


def property_out(prop: Property) -> PropertyOut:
    address = prop.address
    return PropertyOut(
        id=prop.id,
        address=address.normalized_address,
        city_id=address.city_id,
        city=address.city.name,
        municipality_code=address.municipality_code,
        property_type=prop.property_type,
        unit_identifier=prop.unit_identifier,
        rooms=prop.rooms,
        area_m2=prop.area_m2,
        new_construction=prop.new_construction,
        latitude=address.latitude,
        longitude=address.longitude,
        address_enrichments=[
            AddressEnrichmentOut(
                source=item.source.name,
                data_mode=str(item.source_attributes.get("data_mode", "fixture")),
                external_address_id=item.external_address_id,
                canonical_address=item.canonical_address,
                municipality_code=item.municipality_code,
                postal_code=item.postal_code,
                postal_town=item.postal_town,
                status=item.status,
                source_srid=item.source_srid,
                source_easting=item.source_easting,
                source_northing=item.source_northing,
                attribution=item.attribution,
                observed_at=item.observed_at,
                updated_at=item.updated_at,
                register_unit=(
                    RegisterUnitReferenceOut(
                        external_register_unit_id=(
                            item.register_unit_link.external_register_unit_id
                        ),
                        designation=item.register_unit_link.designation,
                        register_unit_type=item.register_unit_link.register_unit_type,
                    )
                    if item.register_unit_link is not None
                    else None
                ),
            )
            for item in address.enrichments
        ],
    )
