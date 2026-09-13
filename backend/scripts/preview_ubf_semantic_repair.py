"""Build a bounded, read-only UBF semantic-repair manifest."""

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from flyttsignal.db.session import SessionLocal
from flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling import (
    parse_rental_object_detail,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DETAILS = (
    BACKEND_ROOT
    / "fixtures"
    / "rental_listings"
    / "uppsala_bostadsformedling"
    / "detail-contract.json"
)
SOURCE_KEY = "uppsala_bostadsformedling_live_rentals"


def _stable_id(kind: str, source_item_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"flyttsignal:ubf-repair:{kind}:{source_item_id}"))


def _group_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_item_id = row["source_item_id"]
        record = grouped.setdefault(
            source_item_id,
            {
                key: row[key]
                for key in (
                    "listing_id",
                    "source_item_id",
                    "raw_item_id",
                    "property_id",
                    "listing_status",
                    "provider_key",
                    "listing_unit_identifier",
                    "listing_new_construction",
                    "project_source_item_id",
                    "property_unit_identifier",
                    "property_new_construction",
                    "property_listing_ids",
                )
            },
        )
        if row.get("event_id") is None:
            continue
        edge = {
            key: row.get(key)
            for key in (
                "event_id",
                "event_type",
                "signal_id",
                "signal_type",
                "signal_status",
                "evidence_superseded_at",
                "signal_current_evidence_count",
                "outcome_ids",
                "feedback_ids",
                "activity_ids",
            )
        }
        if edge not in record.setdefault("edges", []):
            record["edges"].append(edge)
    return grouped


def build_manifest(
    contract: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    generated_at: datetime,
    database_revision: str,
    detail_contract_sha256: str | None = None,
) -> dict[str, Any]:
    grouped = _group_rows(rows)
    targets: list[dict[str, Any]] = []
    for case in contract["cases"]:
        source_item_id = str(case["requested_id"])
        stored = grouped.get(source_item_id)
        if stored is None:
            targets.append(
                {
                    "source_item_id": source_item_id,
                    "disposition": "NOT_FOUND",
                    "actions": [],
                }
            )
            continue

        detail = parse_rental_object_detail(
            case["response"],
            expected_source_item_id=source_item_id,
            expected_provider_key=stored["provider_key"],
        )
        checked_at = datetime.fromisoformat(case["checked_at"].replace("Z", "+00:00"))
        actions: list[dict[str, Any]] = []
        review_reasons: list[str] = []
        if stored["listing_status"] != "ACTIVE":
            review_reasons.append("listing_is_not_active")
        if len(stored["property_listing_ids"]) > 1:
            review_reasons.append("property_is_shared_by_multiple_listings")

        if detail["unit_identifier"] != stored["listing_unit_identifier"]:
            actions.append(
                {
                    "kind": "UPDATE_LISTING_UNIT_IDENTITY",
                    "listing_id": stored["listing_id"],
                    "before": stored["listing_unit_identifier"],
                    "after": detail["unit_identifier"],
                    "namespace": "ubf_landlord_object_number",
                    "requires_property_rematch": True,
                }
            )
        if detail["new_construction"] is True and stored["listing_new_construction"] is not True:
            actions.append(
                {
                    "kind": "UPDATE_LISTING_CONSTRUCTION",
                    "listing_id": stored["listing_id"],
                    "before": stored["listing_new_construction"],
                    "after": True,
                    "observed_at": checked_at.isoformat(),
                }
            )

        replacement_event = next(
            (edge for edge in stored.get("edges", []) if edge["event_type"] == "NEW_BUILD_MOVE_IN"),
            None,
        )
        replacement_signal = next(
            (
                edge
                for edge in stored.get("edges", [])
                if edge["signal_type"] == "NEW_BUILD_MOVE_IN"
            ),
            None,
        )
        replacement_event_id = (
            replacement_event["event_id"]
            if replacement_event
            else _stable_id("event-new-build", source_item_id)
        )
        replacement_signal_id = (
            replacement_signal["signal_id"]
            if replacement_signal
            else _stable_id("signal-new-build", source_item_id)
        )
        if detail["new_construction"] is True:
            actions.append(
                {
                    "kind": "REUSE_OR_CREATE_NEW_BUILD_CHAIN",
                    "event_id": replacement_event_id,
                    "signal_id": replacement_signal_id,
                    "event_exists": replacement_event is not None,
                    "signal_exists": replacement_signal is not None,
                    "valid_from": checked_at.isoformat(),
                }
            )
            for edge in stored.get("edges", []):
                if (
                    edge["event_type"] != "RENTAL_LISTED"
                    or edge["signal_id"] is None
                    or edge["evidence_superseded_at"] is not None
                ):
                    continue
                actions.append(
                    {
                        "kind": "SUPERSEDE_EVIDENCE",
                        "signal_id": edge["signal_id"],
                        "event_id": edge["event_id"],
                        "superseded_by_event_id": replacement_event_id,
                        "superseded_at": checked_at.isoformat(),
                        "reason": "verified_ubf_new_production_semantics",
                        "old_signal_disposition": (
                            "SUPERSEDE"
                            if edge["signal_current_evidence_count"] == 1
                            else "RETAIN_AND_RECOMPUTE"
                        ),
                    }
                )

        protected = {
            "outcome_ids": sorted(
                {
                    item
                    for edge in stored.get("edges", [])
                    for item in edge.get("outcome_ids") or []
                }
            ),
            "feedback_ids": sorted(
                {
                    item
                    for edge in stored.get("edges", [])
                    for item in edge.get("feedback_ids") or []
                }
            ),
            "activity_ids": sorted(
                {
                    item
                    for edge in stored.get("edges", [])
                    for item in edge.get("activity_ids") or []
                }
            ),
        }
        targets.append(
            {
                "source_item_id": source_item_id,
                "listing_id": stored["listing_id"],
                "raw_item_id": stored["raw_item_id"],
                "property_id": stored["property_id"],
                "checked_at": checked_at.isoformat(),
                "source_facts": detail,
                "review_reasons": review_reasons,
                "disposition": "MANUAL_REVIEW" if review_reasons else "PLANNED",
                "actions": actions,
                "protected_history": protected,
            }
        )

    manifest = {
        "mode": "read-only-dry-run",
        "scope": "verified_ubf_detail_contract",
        "source_key": SOURCE_KEY,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "database_revision": database_revision,
        "detail_contract_sha256": detail_contract_sha256,
        "target_count": len(targets),
        "planned_count": sum(target["disposition"] == "PLANNED" for target in targets),
        "manual_review_count": sum(
            target["disposition"] == "MANUAL_REVIEW" for target in targets
        ),
        "not_found_count": sum(target["disposition"] == "NOT_FOUND" for target in targets),
        "targets": targets,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["manifest_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    return manifest


def _read_rows() -> tuple[str, list[dict[str, Any]]]:
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        has_supersession = bool(
            session.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='signal_evidence' AND column_name='superseded_at')"
                )
            )
        )
        superseded_select = (
            "se.superseded_at AS evidence_superseded_at"
            if has_supersession
            else "NULL::timestamptz AS evidence_superseded_at"
        )
        current_predicate = "AND all_se.superseded_at IS NULL" if has_supersession else ""
        query = text(
            f"""
            SELECT l.id::text AS listing_id, l.source_item_id,
                   l.raw_item_id::text AS raw_item_id, l.property_id::text AS property_id,
                   l.status AS listing_status, l.upstream_provider_key AS provider_key,
                   l.unit_identifier AS listing_unit_identifier,
                   l.new_construction AS listing_new_construction,
                   l.project_source_item_id, p.unit_identifier AS property_unit_identifier,
                   p.new_construction AS property_new_construction,
                   ARRAY(SELECT pl.id::text FROM rental_listings pl
                         WHERE pl.property_id=l.property_id ORDER BY pl.id::text)
                       AS property_listing_ids,
                   e.id::text AS event_id, e.event_type::text AS event_type,
                   s.id::text AS signal_id, s.signal_type::text AS signal_type,
                   s.status AS signal_status, {superseded_select},
                   (SELECT count(*) FROM signal_evidence all_se
                    WHERE all_se.signal_id=s.id {current_predicate})
                       AS signal_current_evidence_count,
                   ARRAY(SELECT o.id::text FROM signal_outcomes o
                         WHERE o.signal_id=s.id ORDER BY o.id::text) AS outcome_ids,
                   ARRAY(SELECT f.id::text FROM pilot_signal_feedback f
                         WHERE f.signal_id=s.id ORDER BY f.id::text) AS feedback_ids,
                   ARRAY(SELECT a.id::text FROM pilot_signal_activity a
                         WHERE a.signal_id=s.id ORDER BY a.id::text) AS activity_ids
            FROM rental_listings l
            JOIN sources src ON src.id=l.source_id
            JOIN properties p ON p.id=l.property_id
            LEFT JOIN events e ON e.raw_item_id=l.raw_item_id
            LEFT JOIN signal_evidence se ON se.event_id=e.id
            LEFT JOIN signals s ON s.id=se.signal_id
            WHERE src.key=:source_key
            ORDER BY l.source_item_id, e.id, s.id
            """
        )
        rows = [dict(row) for row in session.execute(query, {"source_key": SOURCE_KEY}).mappings()]
        session.rollback()
    return str(revision), rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--details", type=Path, default=DEFAULT_DETAILS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    contract_bytes = args.details.read_bytes()
    contract = json.loads(contract_bytes)
    revision, rows = _read_rows()
    manifest = build_manifest(
        contract,
        rows,
        generated_at=datetime.now(UTC),
        database_revision=revision,
        detail_contract_sha256=hashlib.sha256(contract_bytes).hexdigest(),
    )
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
