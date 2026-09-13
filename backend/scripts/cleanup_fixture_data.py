"""Audit or remove fixture-only rental data from the development database.

The command is deliberately dry-run by default. Product signals with at least one
live evidence row survive; only their fixture evidence is detached.
"""

import argparse
import json

from sqlalchemy import text

from flyttsignal.db.session import SessionLocal

PREPARE = (
    """
    CREATE TEMP TABLE cleanup_fixture_listings ON COMMIT DROP AS
    SELECT id, raw_item_id, property_id, source_id
    FROM rental_listings
    WHERE data_mode = 'fixture'
    """,
    """
    CREATE TEMP TABLE cleanup_fixture_projects ON COMMIT DROP AS
    SELECT id, raw_item_id, source_id
    FROM rental_projects
    WHERE data_mode = 'fixture'
    """,
    """
    CREATE TEMP TABLE cleanup_fixture_sources ON COMMIT DROP AS
    SELECT DISTINCT s.id
    FROM sources s
    WHERE s.source_type = 'FAKE'
       OR (
            s.enabled = false
            AND (
                EXISTS (SELECT 1 FROM cleanup_fixture_listings fl WHERE fl.source_id = s.id)
                OR EXISTS (SELECT 1 FROM cleanup_fixture_projects fp WHERE fp.source_id = s.id)
            )
            AND NOT EXISTS (
                SELECT 1 FROM rental_listings rl
                WHERE rl.source_id = s.id AND rl.data_mode = 'live'
            )
            AND NOT EXISTS (
                SELECT 1 FROM rental_projects rp
                WHERE rp.source_id = s.id AND rp.data_mode = 'live'
            )
       )
    """,
    """
    CREATE TEMP TABLE cleanup_fixture_raw_items ON COMMIT DROP AS
    SELECT raw_item_id AS id FROM cleanup_fixture_listings
    UNION
    SELECT raw_item_id FROM cleanup_fixture_projects
    UNION
    SELECT ri.id FROM raw_items ri
    WHERE ri.source_id IN (SELECT id FROM cleanup_fixture_sources)
    """,
    """
    CREATE TEMP TABLE cleanup_fixture_events ON COMMIT DROP AS
    SELECT e.id
    FROM events e
    WHERE e.raw_item_id IN (SELECT id FROM cleanup_fixture_raw_items)
       OR e.source_id IN (SELECT id FROM cleanup_fixture_sources)
    """,
    """
    CREATE TEMP TABLE cleanup_affected_signals ON COMMIT DROP AS
    SELECT DISTINCT signal_id
    FROM signal_evidence
    WHERE event_id IN (SELECT id FROM cleanup_fixture_events)
    """,
    """
    CREATE TEMP TABLE cleanup_candidate_properties ON COMMIT DROP AS
    SELECT DISTINCT property_id FROM cleanup_fixture_listings
    UNION
    SELECT DISTINCT e.property_id
    FROM events e
    WHERE e.id IN (SELECT id FROM cleanup_fixture_events)
    """,
    """
    CREATE TEMP TABLE cleanup_candidate_addresses ON COMMIT DROP AS
    SELECT DISTINCT p.address_id
    FROM properties p
    WHERE p.id IN (SELECT property_id FROM cleanup_candidate_properties)
    """,
)


COUNTS = {
    "fixture_sources": "SELECT count(*) FROM cleanup_fixture_sources",
    "fixture_listings": "SELECT count(*) FROM cleanup_fixture_listings",
    "fixture_projects": "SELECT count(*) FROM cleanup_fixture_projects",
    "fixture_events": "SELECT count(*) FROM cleanup_fixture_events",
    "fixture_raw_items": "SELECT count(*) FROM cleanup_fixture_raw_items",
    "affected_signals": "SELECT count(*) FROM cleanup_affected_signals",
    "fixture_only_signals": """
        SELECT count(*)
        FROM cleanup_affected_signals affected
        WHERE NOT EXISTS (
            SELECT 1
            FROM signal_evidence se
            WHERE se.signal_id = affected.signal_id
              AND se.event_id NOT IN (SELECT id FROM cleanup_fixture_events)
        )
    """,
    "mixed_signals_retained": """
        SELECT count(*)
        FROM cleanup_affected_signals affected
        WHERE EXISTS (
            SELECT 1
            FROM signal_evidence se
            WHERE se.signal_id = affected.signal_id
              AND se.event_id NOT IN (SELECT id FROM cleanup_fixture_events)
        )
    """,
}


DELETE = (
    "DELETE FROM signal_evidence WHERE event_id IN (SELECT id FROM cleanup_fixture_events)",
    """
    DELETE FROM score_components sc
    WHERE sc.signal_id IN (SELECT signal_id FROM cleanup_affected_signals)
      AND NOT EXISTS (
          SELECT 1 FROM signal_evidence se WHERE se.signal_id = sc.signal_id
      )
    """,
    """
    DELETE FROM signals s
    WHERE s.id IN (SELECT signal_id FROM cleanup_affected_signals)
      AND NOT EXISTS (
          SELECT 1 FROM signal_evidence se WHERE se.signal_id = s.id
      )
    """,
    "DELETE FROM events WHERE id IN (SELECT id FROM cleanup_fixture_events)",
    "DELETE FROM rental_listings WHERE id IN (SELECT id FROM cleanup_fixture_listings)",
    "DELETE FROM rental_projects WHERE id IN (SELECT id FROM cleanup_fixture_projects)",
    "DELETE FROM source_runs WHERE source_id IN (SELECT id FROM cleanup_fixture_sources)",
    """
    DELETE FROM raw_items ri
    WHERE ri.id IN (SELECT id FROM cleanup_fixture_raw_items)
      AND NOT EXISTS (SELECT 1 FROM events e WHERE e.raw_item_id = ri.id)
      AND NOT EXISTS (SELECT 1 FROM rental_listings rl WHERE rl.raw_item_id = ri.id)
      AND NOT EXISTS (SELECT 1 FROM rental_projects rp WHERE rp.raw_item_id = ri.id)
      AND NOT EXISTS (SELECT 1 FROM benchmark_observations bo WHERE bo.raw_item_id = ri.id)
      AND NOT EXISTS (SELECT 1 FROM spatial_features sf WHERE sf.raw_item_id = ri.id)
      AND NOT EXISTS (SELECT 1 FROM address_enrichments ae WHERE ae.raw_item_id = ri.id)
    """,
    """
    DELETE FROM properties p
    WHERE p.id IN (SELECT property_id FROM cleanup_candidate_properties)
      AND NOT EXISTS (SELECT 1 FROM rental_listings rl WHERE rl.property_id = p.id)
      AND NOT EXISTS (SELECT 1 FROM events e WHERE e.property_id = p.id)
      AND NOT EXISTS (SELECT 1 FROM signals s WHERE s.property_id = p.id)
    """,
    """
    DELETE FROM addresses a
    WHERE a.id IN (SELECT address_id FROM cleanup_candidate_addresses)
      AND NOT EXISTS (SELECT 1 FROM properties p WHERE p.address_id = a.id)
      AND NOT EXISTS (SELECT 1 FROM address_enrichments ae WHERE ae.address_id = a.id)
    """,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the cleanup. Without this flag the transaction is rolled back.",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        for statement in PREPARE:
            session.execute(text(statement))
        report = {
            key: session.execute(text(statement)).scalar_one() for key, statement in COUNTS.items()
        }
        report["mode"] = "apply" if args.apply else "dry-run"

        if args.apply:
            for statement in DELETE:
                session.execute(text(statement))
            session.commit()
        else:
            session.rollback()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
