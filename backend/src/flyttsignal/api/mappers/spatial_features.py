import json

from flyttsignal.api.schemas.spatial_features import SpatialFeatureOut
from flyttsignal.db.models import SpatialFeature


def spatial_feature_out(item: SpatialFeature, geometry_json: str) -> SpatialFeatureOut:
    return SpatialFeatureOut(
        id=item.id,
        source=item.source.name,
        data_mode=item.data_mode,
        dataset_key=item.dataset_key,
        source_item_id=item.source_item_id,
        municipality_code=item.municipality_code,
        feature_type=item.feature_type,
        subtype_code=item.subtype_code,
        subtype_label=item.subtype_label,
        status_code=item.status_code,
        status_label=item.status_label,
        activity_code=item.activity_code,
        activity_label=item.activity_label,
        source_modified_at=item.source_modified_at,
        geometry=json.loads(geometry_json),
        attribution=item.attribution,
        is_baseline=item.is_baseline,
        observed_at=item.observed_at,
        updated_at=item.updated_at,
    )
