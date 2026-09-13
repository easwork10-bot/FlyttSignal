from flyttsignal.api.schemas.housing_providers import HousingProviderOut, ProviderChannelOut
from flyttsignal.db.models import HousingProvider


def housing_provider_out(provider: HousingProvider, city_id: int) -> HousingProviderOut:
    city_link = next(item for item in provider.cities if item.city_id == city_id)
    return HousingProviderOut(
        id=provider.id,
        key=provider.key,
        name=provider.name,
        provider_type=provider.provider_type,
        official_url=provider.official_url,
        city=city_link.city.name,
        discovery_source=city_link.discovery_source,
        evidence_url=city_link.evidence_url,
        verified_at=city_link.verified_at,
        channels=[
            ProviderChannelOut(
                channel_key=channel.channel_key,
                channel_type=channel.channel_type,
                publisher_name=channel.publisher_name,
                url=channel.url,
                coverage=channel.coverage,
                collection_status=channel.collection_status,
                requires_auth=channel.requires_auth,
                requires_agreement=channel.requires_agreement,
                next_action=channel.next_action,
                is_primary=channel.is_primary,
                source_key=channel.source.key if channel.source else None,
            )
            for channel in provider.channels
            if channel.city_id == city_id
        ],
    )
