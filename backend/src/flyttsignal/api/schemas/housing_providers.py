import uuid
from datetime import datetime

from pydantic import BaseModel


class ProviderChannelOut(BaseModel):
    channel_key: str
    channel_type: str
    publisher_name: str
    url: str
    coverage: str
    collection_status: str
    requires_auth: bool
    requires_agreement: bool
    next_action: str | None
    is_primary: bool
    source_key: str | None


class HousingProviderOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    provider_type: str
    official_url: str
    city: str
    discovery_source: str
    evidence_url: str
    verified_at: datetime
    channels: list[ProviderChannelOut]


class HousingProviderList(BaseModel):
    items: list[HousingProviderOut]
    count: int
