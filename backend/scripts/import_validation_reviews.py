"""Validate and optionally apply human-review CSV decisions."""

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from flyttsignal.db.repositories.validation import ValidationRepository
from flyttsignal.db.session import SessionLocal
from flyttsignal.domains.signals.validation import validate_review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True, type=UUID)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    with SessionLocal() as session:
        batch = ValidationRepository(session).batch(args.batch_id)
        if batch is None:
            raise SystemExit("validation batch not found")
        validations = {str(item.signal_id): item for item in batch.validations}
        reviewed = 0
        seen = set()
        for row_number, row in enumerate(rows, start=2):
            signal_id = (row.get("signal_id") or "").strip()
            verdict_raw = (row.get("verdict") or "").strip()
            if not verdict_raw:
                continue
            if signal_id in seen:
                raise SystemExit(f"duplicate signal_id on row {row_number}: {signal_id}")
            seen.add(signal_id)
            validation = validations.get(signal_id)
            if validation is None:
                raise SystemExit(f"signal_id outside batch on row {row_number}: {signal_id}")
            reviewer = (row.get("reviewer") or "").strip()
            if not reviewer:
                raise SystemExit(f"reviewer missing on row {row_number}")
            verdict, issue_codes = validate_review(
                verdict_raw, (row.get("issue_codes") or "").split("|")
            )
            if args.apply:
                validation.review_status = "REVIEWED"
                validation.verdict = verdict
                validation.issue_codes = list(issue_codes)
                validation.notes = (row.get("notes") or "").strip() or None
                validation.reviewer = reviewer
                validation.reviewed_at = datetime.now(UTC)
            reviewed += 1

        if args.apply:
            session.flush()
            if all(item.review_status == "REVIEWED" for item in batch.validations):
                batch.status = "COMPLETE"
                batch.completed_at = datetime.now(UTC)
            session.commit()

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "batch_id": str(args.batch_id),
                "rows_in_file": len(rows),
                "reviewed_rows": reviewed,
                "pending_rows": len(validations) - reviewed,
            }
        )
    )


if __name__ == "__main__":
    main()
