import uuid
from datetime import datetime

from pydantic import BaseModel


class SpatialFeatureOut(BaseModel):
    id: uuid.UUID
    source: str
    data_mode: str
    dataset_key: str
    source_item_id: str
    municipality_code: str
    feature_type: str
    subtype_code: int
    subtype_label: str
    status_code: int
    status_label: str
    activity_code: int | None
    activity_label: str | None
    source_modified_at: datetime | None
    geometry: dict
    attribution: str
    is_baseline: bool
    observed_at: datetime
    updated_at: datetime


class SpatialFeatureList(BaseModel):
    items: list[SpatialFeatureOut]
    count: int
