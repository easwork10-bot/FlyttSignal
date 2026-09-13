"""Preview or persist a reproducible active-dimension validation sample."""

import argparse
import json
from datetime import UTC, datetime

from flyttsignal.db.models import SignalValidation, ValidationBatch
from flyttsignal.db.repositories.validation import ValidationRepository
from flyttsignal.db.session import SessionLocal
from flyttsignal.domains.signals.validation import (
    VALIDATION_RULE_VERSION,
    select_validation_sample,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--city-id", type=int, default=1)
    parser.add_argument("--target-size", type=int, default=60)
    parser.add_argument("--name", default="uppsala-active-dimensions-2026-09-08")
    parser.add_argument("--seed", default="uppsala-active-dimension-validation")
    args = parser.parse_args()

    with SessionLocal() as session:
        repository = ValidationRepository(session)
        existing = repository.batch_by_name(args.name)
        as_of = datetime.now(UTC)
        candidates = repository.candidates(city_id=args.city_id, as_of=as_of)
        selection = select_validation_sample(
            candidates, target_size=args.target_size, seed=args.seed
        )
        batch_id = existing.id if existing else None
        persisted = False
        if args.apply and existing is None:
            batch = ValidationBatch(
                name=args.name,
                city_id=args.city_id,
                rule_version=VALIDATION_RULE_VERSION,
                seed=args.seed,
                target_size=args.target_size,
                population_size=len(candidates),
                status="IN_REVIEW",
                dimension_scope_key="internal-pilot",
                score_run_id=selection.selected[0].candidate.score_run_id,
                score_as_of_date=selection.selected[0].candidate.score_as_of_date,
                definition_set_hash=selection.selected[0].candidate.definition_set_hash,
                selection_manifest={
                    **selection.manifest,
                    "evidence_as_of": as_of.isoformat(),
                },
            )
            batch.validations = [
                SignalValidation(
                    signal_id=item.candidate.signal_id,
                    signal_strength_at_selection=item.candidate.signal_strength,
                    data_confidence_at_selection=item.candidate.data_confidence,
                    timing_at_selection=item.candidate.timing,
                    strength_stratum=item.strength_stratum,
                    inclusion_reasons=list(item.inclusion_reasons),
                    source_keys=list(item.candidate.source_keys),
                    provider_keys=list(item.candidate.provider_keys),
                    classification_tags=list(item.candidate.classification_tags),
                    review_status="PENDING",
                    verdict=None,
                    issue_codes=[],
                    notes=None,
                    reviewer=None,
                    reviewed_at=None,
                )
                for item in selection.selected
            ]
            session.add(batch)
            session.commit()
            batch_id = batch.id
            persisted = True

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "batch_id": str(batch_id) if batch_id else None,
                "existing_batch": existing is not None,
                "persisted": persisted,
                "manifest": {
                    **selection.manifest,
                    "evidence_as_of": as_of.isoformat(),
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
