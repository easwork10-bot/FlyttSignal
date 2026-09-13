import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import structlog
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flyttsignal.classification.service import sync_listing_classifications
from flyttsignal.config import get_settings
from flyttsignal.db.models import (
    Address,
    City,
    Event,
    Property,
    RawItem,
    RentalListing,
    RentalProject,
    RunStatus,
    RunTrigger,
    Signal,
    SignalEvidence,
    Source,
    SourceRun,
)
from flyttsignal.db.repositories.rental_listing_revisions import (
    RentalListingRevisionRepository,
)
from flyttsignal.domains.events.models import EventType
from flyttsignal.domains.events.service import event_type_for
from flyttsignal.domains.listings.classification import (
    classify_listing,
    resolve_construction_state,
)
from flyttsignal.domains.listings.lifecycle import ListingLifecyclePolicy
from flyttsignal.domains.listings.revisions import (
    ListingRevisionCandidate,
    RentalListingRevisionFacts,
    RevisionChangeKind,
    RevisionProvenance,
)
from flyttsignal.domains.properties.matching import (
    PropertyFingerprint,
    choose_strong_match,
)
from flyttsignal.domains.signals.evidence import supersede_evidence
from flyttsignal.domains.signals.inference import (
    RentalInferenceFacts,
    compare_rental_inference,
    infer_rental_signal,
    infer_signal_type,
)
from flyttsignal.ingestion.change_detection import classify_change, content_hash
from flyttsignal.ingestion.contracts import SnapshotEvidence, SourceAdapter
from flyttsignal.ingestion.snapshot_integrity import (
    COMPLETENESS_RULE_VERSION,
    SnapshotAssessment,
    assess_snapshot,
)
from flyttsignal.lifecycle.listings import (
    apply_listing_lifecycle,
    mark_listing_seen,
)
from flyttsignal.measurements.service import sync_lead_time_measurement
from flyttsignal.outcomes.service import (
    record_available_date_change,
    record_cross_source_outcome,
    record_listing_state_outcome,
)

log = structlog.get_logger()


def _revision_facts(listing: RentalListing) -> RentalListingRevisionFacts:
    return RentalListingRevisionFacts(
        listing_status=listing.status,
        available_from=listing.available_from,
        application_deadline=listing.application_deadline,
        new_construction=listing.new_construction,
        categories=tuple(listing.categories),
        unit_identifier=listing.unit_identifier,
    )


def _append_direct_revision(
    session: Session,
    *,
    listing: RentalListing,
    run: SourceRun,
    raw: RawItem,
    change_kind: RevisionChangeKind,
    observed_at: datetime,
) -> None:
    RentalListingRevisionRepository(session).append(
        listing_id=listing.id,
        candidate=ListingRevisionCandidate(
            operation_key=(f"{change_kind.value.lower()}:{run.id}:{listing.source_item_id}"),
            change_kind=change_kind,
            provenance_kind=RevisionProvenance.DIRECT,
            valid_from=observed_at,
            source_run_id=run.id,
            raw_item_id=raw.id,
            content_hash=raw.content_hash,
            raw_payload=raw.raw_payload,
            facts=_revision_facts(listing),
        ),
    )


def _persist_snapshot_integrity(
    run: SourceRun, evidence: SnapshotEvidence, assessment: SnapshotAssessment
) -> None:
    run.snapshot_status = assessment.status.value
    run.requests_attempted = evidence.requests_attempted
    run.requests_succeeded = evidence.requests_succeeded
    run.requests_failed = evidence.requests_failed
    run.pages_expected = evidence.pages_expected
    run.pages_received = evidence.pages_received
    run.items_reported = evidence.items_reported
    run.items_received = evidence.items_received
    run.pagination_complete = evidence.pagination_complete
    run.hit_result_limit = evidence.hit_result_limit
    run.inventory_scope_complete = evidence.inventory_scope_complete
    run.snapshot_reasons = list(assessment.reasons)
    run.snapshot_evidence = dict(evidence.evidence or {})
    run.completeness_rule_version = assessment.rule_version


async def execute_rental_listing_source(
    session: Session,
    source: Source,
    adapter: SourceAdapter,
    *,
    trigger_type: RunTrigger = RunTrigger.MANUAL,
    lifecycle_policy: ListingLifecyclePolicy | None = None,
) -> SourceRun:
    started = time.monotonic()
    run = SourceRun(
        source_id=source.id,
        status=RunStatus.RUNNING,
        trigger_type=trigger_type.value,
        snapshot_status="UNKNOWN",
        snapshot_reasons=["fetch_did_not_return_snapshot_evidence"],
        snapshot_evidence={},
        completeness_rule_version=COMPLETENESS_RULE_VERSION,
    )
    source.status = "RUNNING"
    source.last_run_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    snapshot_evidence: SnapshotEvidence | None = None
    snapshot_assessment: SnapshotAssessment | None = None
    observed_source_item_ids: set[str] = set()
    settings = get_settings()
    try:
        fetch_result = await adapter.fetch()
        payloads = fetch_result.items
        snapshot_evidence = replace(fetch_result.snapshot, items_received=len(payloads))
        snapshot_assessment = assess_snapshot(snapshot_evidence)
        _persist_snapshot_integrity(run, snapshot_evidence, snapshot_assessment)
        for payload in payloads:
            run.items_seen += 1
            parsed = adapter.parse(payload)
            digest = content_hash(parsed)
            raw = session.scalar(
                select(RawItem).where(
                    RawItem.source_id == source.id,
                    RawItem.source_item_id == str(parsed["source_item_id"]),
                )
            )
            source_item_id = str(parsed["source_item_id"])
            observed_source_item_ids.add(source_item_id)
            listing = session.scalar(
                select(RentalListing).where(
                    RentalListing.source_id == source.id,
                    RentalListing.source_item_id == source_item_id,
                    RentalListing.is_historical.is_(False),
                )
            )
            previous_listing_status = listing.status if listing is not None else None
            previous_available_from = listing.available_from if listing is not None else None
            state = classify_change(raw.content_hash if raw else None, digest)
            item = adapter.normalize(parsed)
            if settings.rental_signal_inference_enabled and listing is not None:
                held_legacy = session.scalar(
                    select(Signal.id)
                    .where(
                        Signal.property_id == listing.property_id,
                        Signal.current(),
                        Signal.signal_type.in_(("LIKELY_TENANT_MOVE_OUT", "NEW_BUILD_MOVE_IN")),
                    )
                    .limit(1)
                )
                if held_legacy is not None:
                    log.info("rental_cutover_case_held", listing_id=str(listing.id))
                    run.items_unchanged += 1
                    continue
            effective_new_construction = resolve_construction_state(
                observed=item.new_construction,
                previous=listing.new_construction if listing is not None else None,
                observation_complete=item.new_construction_observation_complete,
            )
            effective_unit_identifier = item.unit_identifier
            if effective_unit_identifier is None and listing is not None:
                effective_unit_identifier = listing.unit_identifier
            if state == "UNCHANGED" and listing is not None:
                run.items_unchanged += 1
                observed_at = datetime.now(UTC)
                listing.unit_identifier = effective_unit_identifier
                listing.rooms = item.rooms
                listing.area_m2 = item.area_m2
                listing.new_construction = effective_new_construction
                mark_listing_seen(listing, observed_at)
                sync_listing_classifications(
                    session,
                    listing,
                    new_construction=effective_new_construction,
                    categories=listing.categories,
                )
                sync_lead_time_measurement(session, listing)
                if settings.rental_listing_revisions_enabled:
                    _append_direct_revision(
                        session,
                        listing=listing,
                        run=run,
                        raw=raw,
                        change_kind=RevisionChangeKind.CONTENT_OBSERVED,
                        observed_at=observed_at,
                    )
                if previous_listing_status == "REMOVED":
                    record_listing_state_outcome(
                        session,
                        listing=listing,
                        outcome_type="LISTING_RELISTED",
                        observed_at=observed_at,
                        dedupe_key=f"listing:{listing.id}:run:{run.id}",
                        evidence={
                            "source_run_id": str(run.id),
                            "stable_source_item_id": listing.source_item_id,
                            "interpretation": "listing_reappeared_not_move_confirmed",
                        },
                    )
                    if settings.rental_listing_revisions_enabled:
                        _append_direct_revision(
                            session,
                            listing=listing,
                            run=run,
                            raw=raw,
                            change_kind=RevisionChangeKind.LISTING_RELISTED,
                            observed_at=observed_at,
                        )
                continue
            if raw is None:
                raw = RawItem(
                    source_id=source.id,
                    source_item_id=source_item_id,
                    source_url=parsed.get("source_url"),
                    content_hash=digest,
                    raw_payload=parsed,
                )
                session.add(raw)
                session.flush()
                run.items_new += 1
            else:
                raw.content_hash = digest
                raw.raw_payload = parsed
                raw.fetched_at = datetime.now(UTC)
                raw.source_url = parsed.get("source_url")
                run.items_changed += 1

            rental_project = None
            if item.project_source_item_id:
                rental_project = session.scalar(
                    select(RentalProject).where(
                        RentalProject.source_item_id == item.project_source_item_id,
                        RentalProject.data_mode == item.data_mode,
                    )
                )
            city = session.scalar(
                select(City).where(City.municipality_code == item.municipality_code)
            )
            if city is None:
                raise ValueError(f"No city configured for {item.municipality_code}")
            address = session.scalar(
                select(Address).where(
                    Address.normalized_address == item.normalized_address,
                    Address.city_id == city.id,
                )
            )
            if address is None:
                geometry = None
                if item.longitude is not None and item.latitude is not None:
                    geometry = WKTElement(f"POINT({item.longitude} {item.latitude})", srid=4326)
                address = Address(
                    raw_address=item.address,
                    normalized_address=item.normalized_address,
                    city_id=city.id,
                    municipality_code=item.municipality_code,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    geometry=geometry,
                )
                session.add(address)
                session.flush()
            kind = (
                EventType.RENTAL_LISTED
                if settings.rental_signal_inference_enabled
                else event_type_for(new_construction=effective_new_construction)
            )
            event = session.scalar(
                select(Event).where(
                    Event.raw_item_id == raw.id,
                    Event.event_type == kind,
                    Event.is_historical.is_(False),
                )
            )
            if event is None:
                incoming = PropertyFingerprint(
                    normalized_address=item.normalized_address,
                    city_id=city.id,
                    property_type=item.property_type,
                    area_m2=item.area_m2,
                    rooms=item.rooms,
                    unit_identifier=effective_unit_identifier,
                )
                # A source's stable listing ID is stronger evidence than address and
                # dimensions. Two different listings from the same source may be
                # separate units with identical public facts, so never merge them.
                occupied_by_same_source = select(RentalListing.property_id).where(
                    RentalListing.source_id == source.id,
                    RentalListing.source_item_id != source_item_id,
                    RentalListing.is_historical.is_(False),
                )
                properties = list(
                    session.scalars(
                        select(Property).where(
                            Property.address_id == address.id,
                            Property.id.not_in(occupied_by_same_source),
                        )
                    )
                )
                candidates = [
                    (
                        candidate,
                        PropertyFingerprint(
                            normalized_address=address.normalized_address,
                            city_id=address.city_id,
                            property_type=candidate.property_type,
                            area_m2=candidate.area_m2,
                            rooms=candidate.rooms,
                            unit_identifier=candidate.unit_identifier,
                        ),
                    )
                    for candidate in properties
                ]
                matched, match = choose_strong_match(incoming, candidates)
                prop = matched if isinstance(matched, Property) else None
                if prop is None:
                    prop = Property(
                        address_id=address.id,
                        property_type=item.property_type,
                        unit_identifier=effective_unit_identifier,
                        rooms=item.rooms,
                        area_m2=item.area_m2,
                        new_construction=effective_new_construction,
                    )
                    session.add(prop)
                    session.flush()
                event = Event(
                    property_id=prop.id,
                    source_id=source.id,
                    raw_item_id=raw.id,
                    upstream_provider_key=item.upstream_provider_key or source.key,
                    event_type=kind,
                    effective_date=item.available_from,
                    event_metadata={
                        "available_from": str(item.available_from) if item.available_from else None,
                        "property_match": match.strength.value,
                        "property_match_reason": match.reason,
                    },
                )
                session.add(event)
                session.flush()
            else:
                prop = session.get(Property, event.property_id)
                if prop is None:
                    raise ValueError(f"Event {event.id} references a missing property")
            event.upstream_provider_key = item.upstream_provider_key or source.key
            if item.upstream_provider_key:
                if listing is None:
                    listing = RentalListing(
                        source_id=source.id,
                        raw_item_id=raw.id,
                        property_id=prop.id,
                        source_item_id=source_item_id,
                        project_source_item_id=item.project_source_item_id,
                        rental_project_id=rental_project.id if rental_project else None,
                        upstream_provider_key=item.upstream_provider_key,
                        upstream_provider_name=item.upstream_provider_name
                        or item.upstream_provider_key,
                        categories=item.categories,
                        data_mode=item.data_mode,
                        attribution=item.attribution or source.name,
                    )
                    session.add(listing)
                listing.raw_item_id = raw.id
                listing.project_source_item_id = item.project_source_item_id
                listing.rental_project_id = rental_project.id if rental_project else None
                listing.property_id = prop.id
                listing.canonical_url = item.source_url
                listing.upstream_provider_key = item.upstream_provider_key
                listing.upstream_provider_name = (
                    item.upstream_provider_name or item.upstream_provider_key
                )
                listing.unit_identifier = effective_unit_identifier
                listing.rooms = item.rooms
                listing.area_m2 = item.area_m2
                listing.new_construction = effective_new_construction
                listing.monthly_rent = item.monthly_rent
                listing.application_deadline = item.application_deadline
                listing.available_from = item.available_from
                listing.categories = item.categories
                listing.data_mode = item.data_mode
                listing.attribution = item.attribution or source.name
                mark_listing_seen(listing, datetime.now(UTC))
                session.flush()
                sync_listing_classifications(
                    session,
                    listing,
                    new_construction=effective_new_construction,
                    categories=item.categories,
                )
                sync_lead_time_measurement(session, listing)
                if settings.rental_listing_revisions_enabled:
                    _append_direct_revision(
                        session,
                        listing=listing,
                        run=run,
                        raw=raw,
                        change_kind=(
                            RevisionChangeKind.LISTING_RELISTED
                            if previous_listing_status == "REMOVED"
                            else RevisionChangeKind.CONTENT_OBSERVED
                        ),
                        observed_at=raw.fetched_at,
                    )
            signal_kind = (
                infer_rental_signal(
                    RentalInferenceFacts(
                        event_type=kind,
                        new_construction=effective_new_construction,
                        classification_tags=frozenset(),
                    )
                ).signal_type
                if settings.rental_signal_inference_enabled
                else infer_signal_type(kind)
            )
            if settings.rental_signal_shadow_enabled:
                shadow = compare_rental_inference(
                    legacy_signal_type=signal_kind,
                    facts=RentalInferenceFacts(
                        event_type=EventType.RENTAL_LISTED,
                        new_construction=effective_new_construction,
                        classification_tags=frozenset(
                            classification.tag
                            for classification in classify_listing(
                                new_construction=effective_new_construction,
                                categories=item.categories,
                            )
                        ),
                    ),
                )
                log.info(
                    "rental_signal_shadow_evaluated",
                    source_key=source.key,
                    source_item_id=source_item_id,
                    legacy_signal_type=(
                        shadow.legacy_signal_type.value
                        if shadow.legacy_signal_type is not None
                        else None
                    ),
                    candidate_signal_type=(
                        shadow.candidate.signal_type.value
                        if shadow.candidate.signal_type is not None
                        else None
                    ),
                    differs=shadow.differs,
                    reason_codes=shadow.candidate.reason_codes,
                    warnings=shadow.candidate.warnings,
                    timing_reference=(
                        shadow.candidate.timing_reference.value
                        if shadow.candidate.timing_reference is not None
                        else None
                    ),
                )
            if signal_kind is None:
                continue
            signal = session.scalar(
                select(Signal).where(
                    Signal.property_id == prop.id, Signal.signal_type == signal_kind
                )
            )
            if signal is None:
                signal = Signal(
                    property_id=prop.id,
                    signal_type=signal_kind,
                    status="ACTIVE",
                )
                session.add(signal)
                session.flush()
            evidence = session.get(SignalEvidence, (signal.id, event.id))
            if evidence is None:
                session.add(
                    SignalEvidence(
                        signal_id=signal.id,
                        event_id=event.id,
                        weight=1,
                        reason=f"{kind.value} supports {signal_kind.value}",
                        valid_from=event.observed_at,
                    )
                )
                session.flush()
            signal.status = "ACTIVE"
            corrected_at = event.observed_at
            conflicting_edges = list(
                session.scalars(
                    select(SignalEvidence)
                    .join(Event, SignalEvidence.event_id == Event.id)
                    .where(
                        Event.raw_item_id == raw.id,
                        Event.is_historical.is_(False),
                        Event.id != event.id,
                        Event.event_type.in_(("RENTAL_LISTED", "NEW_BUILD_MOVE_IN")),
                        SignalEvidence.superseded_at.is_(None),
                    )
                )
            )
            for conflicting_edge in conflicting_edges:
                if not supersede_evidence(
                    conflicting_edge,
                    replacement_event_id=event.id,
                    superseded_at=corrected_at,
                    reason="corrected_source_construction_semantics",
                ):
                    continue
                prior_signal = session.get(Signal, conflicting_edge.signal_id)
                remaining_evidence = session.scalar(
                    select(func.count())
                    .select_from(SignalEvidence)
                    .where(
                        SignalEvidence.signal_id == conflicting_edge.signal_id,
                        SignalEvidence.superseded_at.is_(None),
                    )
                )
                if prior_signal is not None and not remaining_evidence:
                    prior_signal.status = "SUPERSEDED"
            observed_at = datetime.now(UTC)
            if listing is not None and previous_listing_status is not None:
                record_available_date_change(
                    session,
                    listing=listing,
                    previous=previous_available_from,
                    current=item.available_from,
                    observed_at=observed_at,
                    run_id=run.id,
                )
                if previous_listing_status == "REMOVED":
                    record_listing_state_outcome(
                        session,
                        listing=listing,
                        outcome_type="LISTING_RELISTED",
                        observed_at=observed_at,
                        dedupe_key=f"listing:{listing.id}:run:{run.id}",
                        evidence={
                            "source_run_id": str(run.id),
                            "stable_source_item_id": listing.source_item_id,
                            "interpretation": "listing_reappeared_not_move_confirmed",
                        },
                    )
            record_cross_source_outcome(
                session,
                signal_id=signal.id,
                observed_at=observed_at,
            )
        now = datetime.now(UTC)
        run.status = RunStatus.SUCCESS
        run.completed_at = now
        run.duration_ms = round((time.monotonic() - started) * 1000)
        if lifecycle_policy is not None:
            lifecycle_result = apply_listing_lifecycle(
                session,
                source=source,
                current_run=run,
                observed_source_item_ids=observed_source_item_ids,
                policy=lifecycle_policy,
            )
            run.removal_candidates = lifecycle_result.candidates
            run.items_removed = lifecycle_result.removed
            if settings.rental_listing_revisions_enabled:
                for removed_listing_id in lifecycle_result.removed_listing_ids:
                    removed_listing = session.get(RentalListing, removed_listing_id)
                    if removed_listing is None:
                        raise ValueError(f"Lifecycle removed missing listing {removed_listing_id}")
                    removed_raw = session.get(RawItem, removed_listing.raw_item_id)
                    if removed_raw is None:
                        raise ValueError(f"Lifecycle listing {removed_listing_id} has no raw item")
                    _append_direct_revision(
                        session,
                        listing=removed_listing,
                        run=run,
                        raw=removed_raw,
                        change_kind=RevisionChangeKind.LISTING_REMOVED,
                        observed_at=now,
                    )
            if not lifecycle_result.applied:
                log.info(
                    "listing_lifecycle_blocked",
                    source=source.key,
                    reasons=lifecycle_result.reasons,
                )
        source.status = "HEALTHY"
        source.last_success_at = now
        source.next_run_at = now + timedelta(minutes=source.poll_interval_minutes)
        session.commit()
        log.info(
            "source_run_completed",
            source=source.key,
            items_seen=run.items_seen,
            items_new=run.items_new,
            items_changed=run.items_changed,
            items_unchanged=run.items_unchanged,
            removal_candidates=run.removal_candidates,
            items_removed=run.items_removed,
            snapshot_status=run.snapshot_status,
            duration_ms=run.duration_ms,
        )
        return run
    except Exception as exc:
        session.rollback()
        failed_source = session.get(Source, source.id)
        failed_run = session.get(SourceRun, run.id)
        now = datetime.now(UTC)
        failed_source.status = "ERROR"
        failed_source.next_run_at = now + timedelta(minutes=failed_source.poll_interval_minutes)
        failed_run.status = RunStatus.FAILED
        failed_run.completed_at = now
        failed_run.duration_ms = round((time.monotonic() - started) * 1000)
        failed_run.error_message = str(exc)
        if snapshot_evidence is not None and snapshot_assessment is not None:
            _persist_snapshot_integrity(failed_run, snapshot_evidence, snapshot_assessment)
        session.commit()
        log.exception("source_run_failed", source=source.key)
        return failed_run
