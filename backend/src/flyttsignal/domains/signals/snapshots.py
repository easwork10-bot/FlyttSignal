"""Deterministic, score-agnostic feature snapshots."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID

from flyttsignal.domains.signals.features import FEATURE_REGISTRY, FEATURES_BY_NAME

FEATURE_SCHEMA_REVISION = "signal-features/2026-09-02.1"


class FeatureValueState(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    CONFLICTING = "CONFLICTING"


@dataclass(frozen=True)
class FeatureValue:
    state: FeatureValueState
    value: Any = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        item: dict[str, Any] = {"state": self.state.value}
        if self.value is not None:
            item["value"] = _json_value(self.value)
        if self.reason is not None:
            item["reason"] = self.reason
        return item


@dataclass(frozen=True)
class FeatureSnapshot:
    signal_id: UUID
    as_of_date: date
    features: dict[str, FeatureValue]
    schema_revision: str = FEATURE_SCHEMA_REVISION

    def __post_init__(self) -> None:
        expected = {feature.name for feature in FEATURE_REGISTRY}
        actual = set(self.features)
        if actual != expected:
            raise ValueError(
                f"feature snapshot differs from registry: missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )

    def payload(self) -> dict[str, Any]:
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "features": {name: self.features[name].as_dict() for name in sorted(self.features)},
            "schema_revision": self.schema_revision,
            "signal_id": str(self.signal_id),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.payload(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FeatureSnapshot":
        """Restore a persisted snapshot without changing its canonical fingerprint."""

        try:
            features = {
                name: FeatureValue(
                    state=FeatureValueState(item["state"]),
                    value=_decode_feature_value(name, item.get("value")),
                    reason=item.get("reason"),
                )
                for name, item in payload["features"].items()
            }
            return cls(
                signal_id=UUID(payload["signal_id"]),
                as_of_date=date.fromisoformat(payload["as_of_date"]),
                features=features,
                schema_revision=payload["schema_revision"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid persisted feature snapshot payload") from exc


def present(value: Any) -> FeatureValue:
    return FeatureValue(FeatureValueState.PRESENT, value=value)


def missing(reason: str) -> FeatureValue:
    return FeatureValue(FeatureValueState.MISSING, reason=reason)


def unavailable(reason: str) -> FeatureValue:
    return FeatureValue(FeatureValueState.NOT_AVAILABLE, reason=reason)


def scalar(values: list[Any], *, missing_reason: str) -> FeatureValue:
    unique = _unique(values)
    if not unique:
        return missing(missing_reason)
    if len(unique) == 1:
        return present(unique[0])
    return FeatureValue(
        FeatureValueState.CONFLICTING,
        value=unique,
        reason="linked evidence contains different material values",
    )


def value_set(values: list[Any]) -> FeatureValue:
    return present(_unique(values))


def _unique(values: list[Any]) -> list[Any]:
    normalized = {_canonical_scalar(value): value for value in values if value is not None}
    return [normalized[key] for key in sorted(normalized)]


def _canonical_scalar(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _decode_feature_value(name: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [_decode_feature_value(name, item) for item in value]
    value_type = FEATURES_BY_NAME[name].value_type
    if value_type == "date" and isinstance(value, str):
        return date.fromisoformat(value)
    if value_type == "datetime" and isinstance(value, str):
        return datetime.fromisoformat(value)
    if value_type == "uuid" and isinstance(value, str):
        return UUID(value)
    return value
