"""Verify property identity using either historical or current-state semantics."""

import argparse
import json
from collections import Counter
from datetime import UTC
from uuid import UUID

from sqlalchemy import select

from flyttsignal.db.models import Event, RawItem, RentalListing, Signal, SignalEvidence
from flyttsignal.db.repositories.validation import ValidationRepository
from flyttsignal.db.session import SessionLocal
from flyttsignal.normalization.service import normalize_item
from flyttsignal.property_provenance.verification import (
    VerificationMode,
    VerificationStatus,
    evidence_applies,
    verify_projection,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True, type=UUID)
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in VerificationMode],
        default=VerificationMode.AS_OF.value,
    )
    args = parser.parse_args()
    mode = VerificationMode(args.mode)
    mismatches: Counter[str] = Counter()
    unknowns: Counter[str] = Counter()

    with SessionLocal() as session:
        batch = ValidationRepository(session).batch(args.batch_id)
        if batch is None:
            raise SystemExit("validation batch not found")
        as_of = batch.created_at
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=UTC)
        validations = list(batch.validations)
        evidence_rows = 0
        for validation in validations:
            signal = session.get(Signal, validation.signal_id)
            if signal is None:
                mismatches["missing_signal"] += 1
                continue
            evidence_edges = session.scalars(
                select(SignalEvidence).where(SignalEvidence.signal_id == signal.id)
            )
            for evidence in evidence_edges:
                if not evidence_applies(evidence, mode=mode, as_of=as_of):
                    continue
                evidence_rows += 1
                event = session.get(Event, evidence.event_id)
                if event is None:
                    mismatches["missing_event"] += 1
                    continue
                listing = session.scalar(
                    select(RentalListing).where(RentalListing.raw_item_id == event.raw_item_id)
                )
                raw = session.get(RawItem, event.raw_item_id)
                if listing is None or raw is None:
                    mismatches["missing_listing_or_raw"] += 1
                    continue
                item = normalize_item(raw.raw_payload)
                if mode is VerificationMode.AS_OF:
                    unknowns["historical_property_identity_not_captured"] += 1
                    continue
                if signal.property_id != event.property_id:
                    mismatches["signal_event_property"] += 1
                if listing.property_id != event.property_id:
                    mismatches["listing_event_property"] += 1
                if listing.property_id != signal.property_id:
                    mismatches["listing_signal_property"] += 1
                for field in ("unit_identifier", "rooms", "area_m2", "new_construction"):
                    listing_check = verify_projection(
                        mode=mode,
                        current_expected=getattr(item, field),
                        current_actual=getattr(listing, field),
                    )
                    property_check = verify_projection(
                        mode=mode,
                        current_expected=getattr(item, field),
                        current_actual=getattr(signal.property, field),
                    )
                    if listing_check.status is VerificationStatus.FAIL:
                        mismatches[f"listing_{field}"] += 1
                    if property_check.status is VerificationStatus.FAIL:
                        mismatches[f"property_{field}"] += 1
                if signal.property.address.normalized_address != item.normalized_address:
                    mismatches["property_address"] += 1

    overall_status = (
        VerificationStatus.FAIL
        if mismatches
        else VerificationStatus.UNKNOWN
        if unknowns
        else VerificationStatus.PASS
    )
    report = {
        "batch_id": str(args.batch_id),
        "mode": mode.value,
        "as_of": as_of.isoformat(),
        "signals_rechecked": len(validations),
        "evidence_rows_rechecked": evidence_rows,
        "mismatches": dict(sorted(mismatches.items())),
        "unknowns": dict(sorted(unknowns.items())),
        "status": overall_status.value,
        "passed": (
            True
            if overall_status is VerificationStatus.PASS
            else False
            if overall_status is VerificationStatus.FAIL
            else None
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if overall_status is VerificationStatus.FAIL:
        raise SystemExit("Validation-batch property provenance check failed")


if __name__ == "__main__":
    main()
