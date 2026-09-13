from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import RentalListing, RunTrigger, Source, SourceRun
from flyttsignal.domains.listings import lifecycle as listing_lifecycle
from flyttsignal.lifecycle.readiness import evaluate_lifecycle_readiness
from flyttsignal.outcomes.service import record_listing_state_outcome


def mark_listing_seen(listing: RentalListing, observed_at: datetime) -> None:
    listing.last_seen_at = observed_at
    listing.consecutive_misses = 0
    listing.status = "ACTIVE"
    listing.removed_at = None


def apply_listing_lifecycle(
    session: Session,
    *,
    source: Source,
    current_run: SourceRun,
    observed_source_item_ids: set[str],
    policy: listing_lifecycle.ListingLifecyclePolicy,
) -> listing_lifecycle.ListingLifecycleResult:
    """Age only this source's live listings after all current and historical gates pass."""

    if source.key != policy.source_key:
        return listing_lifecycle.ListingLifecycleResult(False, reasons=("policy_source_mismatch",))
    if current_run.trigger_type != RunTrigger.SCHEDULED.value:
        return listing_lifecycle.ListingLifecycleResult(
            False, reasons=("current_run_not_scheduled",)
        )
    if current_run.completeness_rule_version != policy.completeness_rule_version:
        return listing_lifecycle.ListingLifecycleResult(
            False, reasons=("policy_rule_version_mismatch",)
        )

    current_readiness = evaluate_lifecycle_readiness([current_run], required_runs=1)
    if not current_readiness.ready:
        return listing_lifecycle.ListingLifecycleResult(False, reasons=current_readiness.reasons)

    prior_runs = list(
        session.scalars(
            select(SourceRun)
            .where(SourceRun.source_id == source.id, SourceRun.id != current_run.id)
            .order_by(SourceRun.started_at.desc())
            .limit(200)
        )
    )
    prior_readiness = evaluate_lifecycle_readiness(prior_runs)
    if not prior_readiness.ready:
        return listing_lifecycle.ListingLifecycleResult(False, reasons=prior_readiness.reasons)
    if prior_readiness.rule_version != policy.completeness_rule_version:
        return listing_lifecycle.ListingLifecycleResult(
            False, reasons=("prior_rule_version_mismatch",)
        )

    candidates = 0
    removed = 0
    removed_listing_ids = []
    listings = session.scalars(
        select(RentalListing).where(
            RentalListing.source_id == source.id,
            RentalListing.data_mode == "live",
            RentalListing.status.in_(("ACTIVE", "REMOVAL_CANDIDATE")),
        )
    )
    for listing in listings:
        if listing.source_item_id in observed_source_item_ids:
            continue
        listing.consecutive_misses += 1
        listing.status = listing_lifecycle.listing_status_after_miss(
            listing.consecutive_misses, policy.grace_runs
        )
        if listing.status == "REMOVED":
            listing.removed_at = current_run.completed_at
            record_listing_state_outcome(
                session,
                listing=listing,
                outcome_type="LISTING_REMOVED",
                observed_at=current_run.completed_at,
                dedupe_key=f"listing:{listing.id}:run:{current_run.id}",
                evidence={
                    "source_run_id": str(current_run.id),
                    "consecutive_complete_misses": listing.consecutive_misses,
                    "interpretation": "listing_removed_not_move_confirmed",
                },
            )
            removed += 1
            removed_listing_ids.append(listing.id)
        else:
            candidates += 1

    return listing_lifecycle.ListingLifecycleResult(
        True,
        candidates=candidates,
        removed=removed,
        removed_listing_ids=tuple(removed_listing_ids),
    )
