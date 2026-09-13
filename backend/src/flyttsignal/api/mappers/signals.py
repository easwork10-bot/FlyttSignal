from flyttsignal.api.mappers.properties import property_out
from flyttsignal.api.schemas.signals import (
    ActiveDimensionsOut,
    EvidenceOut,
    SignalOut,
    SignalTimingOut,
    TimingFactOut,
)
from flyttsignal.db.models import Signal
from flyttsignal.db.repositories.score_activations import ActiveSignalDimensions
from flyttsignal.domains.signals.resolved_timing import ResolvedSignalTiming


def signal_out(
    signal: Signal,
    dimensions: ActiveSignalDimensions,
    *,
    detail: bool = False,
    timing: ResolvedSignalTiming | None = None,
) -> SignalOut:
    evidence = [
        EvidenceOut(
            event_id=item.event.id,
            raw_item_id=item.event.raw_item_id,
            source_item_id=item.event.raw_item.source_item_id,
            event_type=item.event.event_type.value,
            source=item.event.source.name,
            observed_at=item.event.observed_at,
            effective_date=item.event.effective_date,
            weight=item.weight,
            reason=item.reason,
        )
        for item in signal.evidence
        if item.superseded_at is None
    ]
    return SignalOut(
        id=signal.id,
        property_id=signal.property_id,
        signal_type=signal.signal_type.value,
        status=signal.status,
        active_dimensions=ActiveDimensionsOut(**dimensions.__dict__),
        timing=_timing_out(timing) if timing else None,
        estimated_move_from=signal.estimated_move_from,
        estimated_move_to=signal.estimated_move_to,
        created_at=signal.created_at,
        updated_at=signal.updated_at,
        property=property_out(signal.property),
        evidence_count=len(evidence),
        evidence=evidence if detail else [],
    )


def _timing_out(timing: ResolvedSignalTiming) -> SignalTimingOut:
    def fact_out(fact) -> TimingFactOut:
        return TimingFactOut(
            type=fact.fact_type.value,
            state=fact.state.value,
            date=fact.value,
            observation_ids=list(fact.observation_ids),
            conflicting_dates=list(fact.conflicting_values),
            warnings=list(fact.warnings),
        )

    return SignalTimingOut(
        primary=fact_out(timing.primary),
        facts=[fact_out(fact) for fact in timing.facts],
        mode=timing.mode.value,
        as_of=timing.as_of,
        warnings=list(timing.warnings),
    )
