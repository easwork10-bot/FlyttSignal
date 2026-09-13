import enum
from dataclasses import dataclass
from decimal import Decimal


class MatchStrength(enum.StrEnum):
    STRONG_MATCH = "STRONG_MATCH"
    UNCERTAIN_MATCH = "UNCERTAIN_MATCH"
    NO_MATCH = "NO_MATCH"


@dataclass(frozen=True)
class PropertyFingerprint:
    normalized_address: str
    city_id: int
    property_type: str
    area_m2: Decimal | None = None
    rooms: Decimal | None = None
    unit_identifier: str | None = None


@dataclass(frozen=True)
class MatchDecision:
    strength: MatchStrength
    reason: str


ONE_SIDED_UNIT_REASON = "Unit identifier is present on only one side; automatic merge refused"


def classify_property_match(
    incoming: PropertyFingerprint, candidate: PropertyFingerprint
) -> MatchDecision:
    if (
        incoming.normalized_address != candidate.normalized_address
        or incoming.city_id != candidate.city_id
    ):
        return MatchDecision(MatchStrength.NO_MATCH, "Address or city differs")
    if incoming.property_type != candidate.property_type:
        return MatchDecision(MatchStrength.NO_MATCH, "Property type differs")
    if (
        incoming.unit_identifier
        and candidate.unit_identifier
        and incoming.unit_identifier != candidate.unit_identifier
    ):
        return MatchDecision(MatchStrength.NO_MATCH, "Unit identifier differs")
    if bool(incoming.unit_identifier) != bool(candidate.unit_identifier):
        return MatchDecision(
            MatchStrength.UNCERTAIN_MATCH,
            ONE_SIDED_UNIT_REASON,
        )
    if incoming.area_m2 is not None and candidate.area_m2 is not None:
        if abs(incoming.area_m2 - candidate.area_m2) > Decimal("1.0"):
            return MatchDecision(MatchStrength.NO_MATCH, "Area differs by more than 1 m²")
    if incoming.rooms is not None and candidate.rooms is not None:
        if abs(incoming.rooms - candidate.rooms) > Decimal("0.5"):
            return MatchDecision(MatchStrength.NO_MATCH, "Room count differs")

    same_unit = bool(
        incoming.unit_identifier
        and candidate.unit_identifier
        and incoming.unit_identifier == candidate.unit_identifier
    )
    complete_dimensions = all(
        value is not None
        for value in (incoming.area_m2, candidate.area_m2, incoming.rooms, candidate.rooms)
    )
    if same_unit or complete_dimensions:
        basis = "same unit identifier" if same_unit else "compatible area and room count"
        return MatchDecision(MatchStrength.STRONG_MATCH, f"Exact address with {basis}")
    return MatchDecision(
        MatchStrength.UNCERTAIN_MATCH,
        "Exact address but insufficient attributes for an automatic merge",
    )


def choose_strong_match[Candidate](
    incoming: PropertyFingerprint,
    candidates: list[tuple[Candidate, PropertyFingerprint]],
) -> tuple[Candidate | None, MatchDecision]:
    decisions = [
        (candidate, classify_property_match(incoming, fingerprint))
        for candidate, fingerprint in candidates
    ]
    strong = [
        candidate
        for candidate, decision in decisions
        if decision.strength == MatchStrength.STRONG_MATCH
    ]
    if len(strong) == 1:
        decision = next(decision for candidate, decision in decisions if candidate is strong[0])
        return strong[0], decision
    if len(strong) > 1:
        return None, MatchDecision(
            MatchStrength.UNCERTAIN_MATCH, "Multiple strong candidates; automatic merge refused"
        )
    uncertain = next(
        (
            decision
            for _, decision in decisions
            if decision.strength == MatchStrength.UNCERTAIN_MATCH
        ),
        None,
    )
    return None, uncertain or MatchDecision(MatchStrength.NO_MATCH, "No compatible property found")


def resolve_current_property_match(
    *,
    recorded_match: str | None,
    recorded_reason: str | None,
    listing_unit_identifier: str | None,
    property_unit_identifier: str | None,
    ownership_consistent: bool,
) -> str | None:
    """Project a safely separated one-sided match as current NO_MATCH, retaining audit metadata."""

    if (
        recorded_match == MatchStrength.UNCERTAIN_MATCH
        and recorded_reason == ONE_SIDED_UNIT_REASON
        and ownership_consistent
        and listing_unit_identifier
        and listing_unit_identifier == property_unit_identifier
    ):
        return MatchStrength.NO_MATCH
    return recorded_match
