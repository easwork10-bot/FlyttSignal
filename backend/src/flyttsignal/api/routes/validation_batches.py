import uuid

from fastapi import APIRouter, HTTPException

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.validation_batches import (
    ValidationBatchOut,
    ValidationBatchSummaryOut,
)
from flyttsignal.db.repositories.validation import ValidationRepository

router = APIRouter()


def _validation_batch_summary(batch) -> ValidationBatchSummaryOut:
    reviewed_count = sum(item.review_status == "REVIEWED" for item in batch.validations)
    verdict_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    for item in batch.validations:
        if item.verdict:
            verdict_counts[item.verdict] = verdict_counts.get(item.verdict, 0) + 1
        for code in item.issue_codes:
            issue_counts[code] = issue_counts.get(code, 0) + 1
    return ValidationBatchSummaryOut(
        id=batch.id,
        name=batch.name,
        city_id=batch.city_id,
        rule_version=batch.rule_version,
        dimension_scope_key=batch.dimension_scope_key,
        score_run_id=batch.score_run_id,
        score_as_of_date=batch.score_as_of_date,
        definition_set_hash=batch.definition_set_hash,
        seed=batch.seed,
        target_size=batch.target_size,
        population_size=batch.population_size,
        status=batch.status,
        reviewed_count=reviewed_count,
        pending_count=len(batch.validations) - reviewed_count,
        verdict_counts=dict(sorted(verdict_counts.items())),
        issue_counts=dict(sorted(issue_counts.items())),
        created_at=batch.created_at,
        completed_at=batch.completed_at,
    )


@router.get(
    "/validation-batches",
    response_model=list[ValidationBatchSummaryOut],
    operation_id="listValidationBatches",
)
def list_validation_batches(db: Db):
    return [_validation_batch_summary(batch) for batch in ValidationRepository(db).batches()]


@router.get(
    "/validation-batches/{batch_id}",
    response_model=ValidationBatchOut,
    operation_id="getValidationBatch",
)
def get_validation_batch(batch_id: uuid.UUID, db: Db):
    batch = ValidationRepository(db).batch(batch_id)
    if batch is None:
        raise HTTPException(404, "Validation batch not found")
    summary = _validation_batch_summary(batch)
    return ValidationBatchOut(
        **summary.model_dump(),
        selection_manifest=batch.selection_manifest,
        items=sorted(
            batch.validations,
            key=lambda item: (
                item.strength_stratum or item.score_stratum or "",
                -(item.signal_strength_at_selection or item.score_at_selection or 0),
                str(item.signal_id),
            ),
        ),
    )
