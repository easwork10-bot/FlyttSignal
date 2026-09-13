from dataclasses import dataclass
from enum import StrEnum

from flyttsignal.domains.events.models import EventType
from flyttsignal.domains.signals.models import SignalType
from flyttsignal.domains.signals.timing import TimingFactType


class TurnoverEvidence(StrEnum):
    """Evidence already validated as referring to the same rental unit."""

    LEASE_TERMINATION_OBSERVED = "LEASE_TERMINATION_OBSERVED"
    EXPLICIT_RELETTING_EVIDENCE = "EXPLICIT_RELETTING_EVIDENCE"
    VERIFIED_TENANCY_CHANGE = "VERIFIED_TENANCY_CHANGE"


@dataclass(frozen=True)
class RentalInferenceFacts:
    event_type: EventType
    new_construction: bool | None
    classification_tags: frozenset[str]
    turnover_evidence: frozenset[TurnoverEvidence] = frozenset()


@dataclass(frozen=True)
class InferenceDecision:
    signal_type: SignalType | None
    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    timing_reference: TimingFactType | None


@dataclass(frozen=True)
class ShadowInferenceComparison:
    legacy_signal_type: SignalType | None
    candidate: InferenceDecision

    @property
    def differs(self) -> bool:
        return self.legacy_signal_type != self.candidate.signal_type


def infer_rental_signal(facts: RentalInferenceFacts) -> InferenceDecision:
    """Infer a rental hypothesis without claiming a contract or physical move."""

    if facts.event_type != EventType.RENTAL_LISTED:
        return InferenceDecision(None, (), (), None)

    reasons = ["RENTAL_LISTING_OBSERVED"]
    warnings: list[str] = []
    _append_classification_reasons(facts.classification_tags, reasons)

    if facts.new_construction is True:
        reasons.append("EXPLICIT_NEW_CONSTRUCTION")
        return InferenceDecision(
            SignalType.POTENTIAL_NEW_BUILD_MOVE_IN,
            tuple(reasons),
            tuple(warnings),
            TimingFactType.ADVERTISED_AVAILABLE_FROM,
        )

    if facts.new_construction is False:
        reasons.append("EXPLICIT_NOT_NEW_CONSTRUCTION")
    else:
        reasons.append("CONSTRUCTION_STATUS_UNKNOWN")
        warnings.append("NEW_CONSTRUCTION_NOT_ESTABLISHED")

    if facts.turnover_evidence:
        reasons.extend(sorted(item.value for item in facts.turnover_evidence))
        signal_type = SignalType.LIKELY_RENTAL_TURNOVER
    else:
        reasons.append("TURNOVER_EVIDENCE_MISSING")
        signal_type = SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE

    return InferenceDecision(
        signal_type,
        tuple(reasons),
        tuple(warnings),
        TimingFactType.ADVERTISED_AVAILABLE_FROM,
    )


def compare_rental_inference(
    *, legacy_signal_type: SignalType | None, facts: RentalInferenceFacts
) -> ShadowInferenceComparison:
    return ShadowInferenceComparison(
        legacy_signal_type=legacy_signal_type,
        candidate=infer_rental_signal(facts),
    )


def _append_classification_reasons(tags: frozenset[str], reasons: list[str]) -> None:
    mapping = {
        "ROOM": "ROOM_LISTING",
        "SHORT_TERM": "SHORT_TERM_CONTRACT",
        "STUDENT_HOUSING": "STUDENT_HOUSING",
        "SENIOR_HOUSING": "SENIOR_HOUSING",
        "YOUTH_HOUSING": "YOUTH_HOUSING",
    }
    reasons.extend(mapping[tag] for tag in sorted(tags) if tag in mapping)


def infer_signal_type(event_type: EventType) -> SignalType | None:
    """Mapping used by gated legacy consumers and non-rental inference."""

    if event_type == EventType.RENTAL_LISTED:
        return SignalType.LIKELY_TENANT_MOVE_OUT
    if event_type == EventType.NEW_BUILD_MOVE_IN:
        return SignalType.NEW_BUILD_MOVE_IN
    if event_type == EventType.SALE_SOLD:
        return SignalType.LIKELY_HOMEOWNER_MOVE
    return None
