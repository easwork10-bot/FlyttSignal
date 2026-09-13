import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from flyttsignal.api.schemas.score_runs import ScoreDefinitionOut


class ActivatedScoreDefinitionOut(BaseModel):
    dimension: str
    definition: ScoreDefinitionOut
    activated_at: datetime
    decision_reason: str


class ScoreActivationSetOut(BaseModel):
    scope_type: Literal["INTERNAL_PILOT"]
    scope_key: str
    city_id: int
    decision_run_id: uuid.UUID
    as_of_date: date
    serving_mode: Literal["INTERNAL_PILOT"] = "INTERNAL_PILOT"
    activations: list[ActivatedScoreDefinitionOut]
