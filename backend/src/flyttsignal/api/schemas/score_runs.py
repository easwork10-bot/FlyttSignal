import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ScoreRunOut(BaseModel):
    id: uuid.UUID
    city_id: int
    as_of_date: date
    feature_schema_revision: str
    definition_set_hash: str
    population_fingerprint: str
    population_size: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScoreDefinitionOut(BaseModel):
    id: uuid.UUID
    dimension: str
    definition_revision: str
    parameter_hash: str
    feature_schema_revision: str
    engine_revision: str
    status: str
    model_config = ConfigDict(from_attributes=True)


class SignalDimensionEvaluationOut(BaseModel):
    dimension: str
    score: int
    components: list[dict]
    warnings: list[str]
    definition: ScoreDefinitionOut
    model_config = ConfigDict(from_attributes=True)


class SignalDimensionSetOut(BaseModel):
    run_id: uuid.UUID
    signal_id: uuid.UUID
    as_of_date: date
    feature_snapshot_id: uuid.UUID
    feature_snapshot_hash: str
    dimensions: list[SignalDimensionEvaluationOut]
