from dataclasses import dataclass
from enum import StrEnum


class Targetability(StrEnum):
    UNIT = "UNIT"
    BUILDING = "BUILDING"
    AREA = "AREA"
    NONE = "NONE"


@dataclass(frozen=True)
class TargetabilityFacts:
    stable_unit_identity: bool
    exact_building_identity: bool
    reliable_area_identity: bool
    identity_conflict: bool = False


@dataclass(frozen=True)
class TargetabilityDecision:
    level: Targetability
    reason_codes: tuple[str, ...]


def decide_targetability(facts: TargetabilityFacts) -> TargetabilityDecision:
    """Decide usable geographic precision independently of signal meaning."""

    if facts.identity_conflict:
        return TargetabilityDecision(Targetability.NONE, ("IDENTITY_CONFLICT",))
    if facts.stable_unit_identity:
        return TargetabilityDecision(Targetability.UNIT, ("STABLE_UNIT_IDENTITY",))
    if facts.exact_building_identity:
        return TargetabilityDecision(Targetability.BUILDING, ("EXACT_BUILDING_IDENTITY",))
    if facts.reliable_area_identity:
        return TargetabilityDecision(Targetability.AREA, ("RELIABLE_AREA_IDENTITY",))
    return TargetabilityDecision(Targetability.NONE, ("TARGET_IDENTITY_UNUSABLE",))
