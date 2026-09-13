from datetime import UTC, datetime

from fastapi import APIRouter

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.rental_coverage import RentalCoverageOut, RentalCoverageProviderOut
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get(
    "/rental-coverage",
    response_model=RentalCoverageOut,
    operation_id="getRentalCoverage",
)
def get_rental_coverage(db: Db, city_id: int = 1):
    repository = DashboardRepository(db)
    providers = repository.housing_providers(city_id)
    inventory = repository.live_provider_inventory(city_id)
    observed: dict[str, dict] = {}
    for key, name, publisher, count in inventory:
        item = observed.setdefault(key, {"name": name, "count": 0, "publishers": set()})
        item["count"] += count
        item["publishers"].add(publisher)
    known_keys = {provider.key for provider in providers}
    rows: list[RentalCoverageProviderOut] = []
    for provider in providers:
        live = observed.get(provider.key)
        collectors = sorted(
            {
                channel.source.key
                for channel in provider.channels
                if channel.city_id == city_id
                and channel.source is not None
                and channel.source.enabled
            }
        )
        count = live["count"] if live else 0
        if count:
            status = "LIVE_INVENTORY"
            gap_reason = None
        elif collectors:
            status = "CONNECTED_NO_CURRENT_LISTINGS"
            gap_reason = (
                "Kopplad källa finns men gav ingen aktiv liveannons i senaste inventeringen."
            )
        else:
            status = "MISSING_COLLECTOR"
            gap_reason = "Ingen insamlingskälla är kopplad till hyresvärden."
        rows.append(
            RentalCoverageProviderOut(
                key=provider.key,
                name=provider.name,
                known_provider=True,
                live_listing_count=count,
                publishers=sorted(live["publishers"]) if live else [],
                collector_keys=collectors,
                status=status,
                gap_reason=gap_reason,
            )
        )
    for key in sorted(observed.keys() - known_keys):
        live = observed[key]
        rows.append(
            RentalCoverageProviderOut(
                key=key,
                name=live["name"],
                known_provider=False,
                live_listing_count=live["count"],
                publishers=sorted(live["publishers"]),
                collector_keys=[],
                status="LIVE_DISCOVERED",
                gap_reason="Observerad live men saknas ännu i den granskade hyresvärdskatalogen.",
            )
        )
    represented = sum(row.live_listing_count > 0 for row in rows if row.known_provider)
    city_name = providers[0].cities[0].city.name if providers else str(city_id)
    return RentalCoverageOut(
        city=city_name,
        generated_at=datetime.now(UTC),
        known_provider_count=len(providers),
        represented_known_provider_count=represented,
        missing_known_provider_count=len(providers) - represented,
        observed_provider_count=len(observed),
        providers=rows,
    )
