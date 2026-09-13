"""Stable score-definition identity and reproducibility metadata."""

import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid5

DEFINITION_NAMESPACE = UUID("45554542-2c60-4ec7-a890-4d73ccfb0925")


class ScoreDimension(StrEnum):
    SIGNAL_STRENGTH = "SIGNAL_STRENGTH"
    DATA_CONFIDENCE = "DATA_CONFIDENCE"
    TIMING = "TIMING"


class ScoreDefinitionStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class DefinitionMetadata:
    """Immutable identity for one dimension policy and its exact parameters."""

    definition_id: UUID
    definition_revision: str
    parameter_hash: str
    feature_schema_revision: str
    engine_revision: str
    as_of: date
    dimension: ScoreDimension
    status: ScoreDefinitionStatus

    @classmethod
    def from_parameters(
        cls,
        *,
        definition_revision: str,
        parameters: dict[str, Any],
        feature_schema_revision: str,
        engine_revision: str,
        as_of: date,
        dimension: ScoreDimension,
        status: ScoreDefinitionStatus = ScoreDefinitionStatus.CANDIDATE,
    ) -> "DefinitionMetadata":
        parameter_hash = cls.compute_parameter_hash(parameters)
        identity = ":".join(
            (
                dimension.value,
                definition_revision,
                parameter_hash,
                feature_schema_revision,
                engine_revision,
            )
        )
        return cls(
            definition_id=uuid5(DEFINITION_NAMESPACE, identity),
            definition_revision=definition_revision,
            parameter_hash=parameter_hash,
            feature_schema_revision=feature_schema_revision,
            engine_revision=engine_revision,
            as_of=as_of,
            dimension=dimension,
            status=status,
        )

    @staticmethod
    def compute_parameter_hash(parameters: dict[str, Any]) -> str:
        canonical = json.dumps(
            parameters,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return sha256(canonical.encode()).hexdigest()
