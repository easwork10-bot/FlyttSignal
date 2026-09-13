from datetime import datetime

from pydantic import BaseModel


class RentalCoverageProviderOut(BaseModel):
    key: str
    name: str
    known_provider: bool
    live_listing_count: int
    publishers: list[str]
    collector_keys: list[str]
    status: str
    gap_reason: str | None


class RentalCoverageOut(BaseModel):
    city: str
    generated_at: datetime
    known_provider_count: int
    represented_known_provider_count: int
    missing_known_provider_count: int
    observed_provider_count: int
    providers: list[RentalCoverageProviderOut]
