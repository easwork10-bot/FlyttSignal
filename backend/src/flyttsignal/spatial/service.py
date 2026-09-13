from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class SpatialFeatureInput(BaseModel):
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
    geometry_wkt: str
    geometry_geojson: dict[str, Any]
    attribution: str
    source_attributes: dict[str, Any]
    data_mode: Literal["fixture", "live"]
