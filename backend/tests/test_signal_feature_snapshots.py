from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import sqlite

from flyttsignal.db.models import Event, Signal
from flyttsignal.db.repositories.feature_snapshots import FeatureSnapshotRepository
from flyttsignal.domains.signals.features import FEATURE_REGISTRY
from flyttsignal.domains.signals.snapshots import (
    FeatureSnapshot,
    FeatureValueState,
    missing,
    present,
    scalar,
    unavailable,
)

SIGNAL_ID = UUID("11111111-1111-1111-1111-111111111111")


def _features():
    return {feature.name: missing("fixture has no value") for feature in FEATURE_REGISTRY}


def test_snapshot_hash_is_canonical_and_changes_with_material_input() -> None:
    features = _features()
    features["signal_status"] = present("ACTIVE")
    first = FeatureSnapshot(SIGNAL_ID, date(2026, 9, 2), features)
    reordered = FeatureSnapshot(SIGNAL_ID, date(2026, 9, 2), dict(reversed(features.items())))
    assert first.fingerprint() == reordered.fingerprint()

    changed = dict(features)
    changed["signal_status"] = present("ARCHIVED")
    assert (
        first.fingerprint() != FeatureSnapshot(SIGNAL_ID, date(2026, 9, 2), changed).fingerprint()
    )


def test_snapshot_requires_exact_feature_registry() -> None:
    with pytest.raises(ValueError, match="differs from registry"):
        FeatureSnapshot(SIGNAL_ID, date(2026, 9, 2), {"signal_status": present("ACTIVE")})


def test_feature_value_states_distinguish_missing_unavailable_and_conflict() -> None:
    assert missing("not observed").as_dict() == {
        "state": FeatureValueState.MISSING.value,
        "reason": "not observed",
    }
    assert unavailable("not implemented").as_dict() == {
        "state": FeatureValueState.NOT_AVAILABLE.value,
        "reason": "not implemented",
    }
    conflict = scalar(["B", "A", "B"], missing_reason="none")
    assert conflict.state is FeatureValueState.CONFLICTING
    assert conflict.as_dict()["value"] == ["A", "B"]


def test_datetime_serialization_keeps_timezone_and_is_stable() -> None:
    features = _features()
    features["first_seen_at"] = present(datetime(2026, 9, 2, 8, tzinfo=UTC))
    snapshot = FeatureSnapshot(SIGNAL_ID, date(2026, 9, 2), features)
    assert snapshot.payload()["features"]["first_seen_at"]["value"] == ("2026-09-02T08:00:00+00:00")


def test_current_state_capture_cannot_be_backdated() -> None:
    repository = FeatureSnapshotRepository(object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="historical replay"):
        repository.build_current(
            city_id=1,
            as_of_date=date(2026, 9, 1),
            captured_at=datetime(2026, 9, 2, 8, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    ("change", "included"),
    [
        ("", True),
        ("UPDATE rental_listings SET new_construction = 0", True),
        ("UPDATE signals SET signal_type = 'LIKELY_TENANT_MOVE_OUT'", False),
        ("UPDATE signals SET signal_type = 'NEW_BUILD_MOVE_IN'", False),
        ("UPDATE signals SET signal_type = 'LIKELY_RENTAL_TURNOVER'", False),
        ("UPDATE signals SET signal_type = 'POTENTIAL_NEW_BUILD_MOVE_IN'", False),
        ("UPDATE rental_listings SET new_construction = 1", False),
        (
            "UPDATE signals SET signal_type = 'POTENTIAL_NEW_BUILD_MOVE_IN';"
            "UPDATE rental_listings SET new_construction = 1",
            True,
        ),
        (
            "INSERT INTO events VALUES "
            "('derived','p','r','src','NEW_BUILD_MOVE_IN','2026-09-01',0);"
            "INSERT INTO signal_evidence VALUES ('s','derived','2026-09-01',NULL)",
            True,
        ),
        ("UPDATE signals SET superseded_at = '2026-09-01'", False),
        ("UPDATE signals SET status = 'SUPERSEDED'", False),
        ("UPDATE events SET event_type = 'NEW_BUILD_MOVE_IN'", False),
        ("UPDATE events SET is_historical = 1", False),
        ("UPDATE rental_listings SET is_historical = 1", False),
        ("UPDATE events SET observed_at = '2027-01-01'", False),
        ("UPDATE signal_evidence SET superseded_at = '2026-09-01'", False),
        ("UPDATE signal_evidence SET valid_from = '2027-01-01'", False),
        ("DELETE FROM signal_evidence", False),
        ("UPDATE raw_items SET raw_payload = NULL", False),
        ("UPDATE raw_items SET source_id = 'other'", False),
        ("UPDATE raw_items SET source_item_id = 'other'", False),
        ("UPDATE rental_listings SET property_id = 'other'", False),
        ("UPDATE rental_listings SET data_mode = 'fixture'", False),
        ("INSERT INTO signals VALUES ('held','p','NEW_BUILD_MOVE_IN','ACTIVE',NULL)", False),
        ("INSERT INTO signals VALUES ('held','p','NEW_BUILD_MOVE_IN','ACTIVE','2026-09-01')", True),
    ],
)
def test_current_scoring_query_requires_new_semantics_and_factual_lineage(change, included):
    # Execute the actual repository predicate; no geometry extension or live DB needed.
    queries = []
    session = SimpleNamespace(
        execute=lambda query: queries.append(query) or SimpleNamespace(all=lambda: [])
    )
    FeatureSnapshotRepository(session).build_current(
        city_id=1,
        as_of_date=date(2026, 9, 2),
        captured_at=datetime(2026, 9, 2, 8, tzinfo=UTC),
    )
    query = queries[0].with_only_columns(Signal.id, Event.id).order_by(None)
    sql = str(query.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for statement in (
            "CREATE TABLE signals (id,property_id,signal_type,status,superseded_at)",
            "CREATE TABLE properties (id,address_id)",
            "CREATE TABLE addresses (id,city_id)",
            "CREATE TABLE events (id,property_id,raw_item_id,source_id,event_type,observed_at)",
            "CREATE TABLE signal_evidence (signal_id,event_id,valid_from,superseded_at)",
            "CREATE TABLE rental_listings (raw_item_id,property_id,source_id,source_item_id,"
            "data_mode,new_construction)",
            "CREATE TABLE raw_items (id,source_id,source_item_id,raw_payload,content_hash)",
            "CREATE TABLE sources (id,key)",
            "INSERT INTO signals VALUES ('s','p','POTENTIAL_RENTAL_TENANCY_CHANGE','ACTIVE',NULL)",
            "INSERT INTO properties VALUES ('p','a')",
            "INSERT INTO addresses VALUES ('a',1)",
            "INSERT INTO events VALUES ('e','p','r','src','RENTAL_LISTED','2026-09-01')",
            "INSERT INTO signal_evidence VALUES ('s','e','2026-09-01',NULL)",
            "INSERT INTO rental_listings VALUES ('r','p','src','item','live',NULL)",
            "INSERT INTO raw_items VALUES ('r','src','item','{}','hash')",
            "INSERT INTO sources VALUES ('src','channel')",
        ):
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql("ALTER TABLE events ADD COLUMN is_historical BOOLEAN DEFAULT 0")
        connection.exec_driver_sql(
            "ALTER TABLE rental_listings ADD COLUMN is_historical BOOLEAN DEFAULT 0"
        )
        for statement in change.split(";"):
            if statement:
                connection.exec_driver_sql(statement)
        assert len(connection.exec_driver_sql(sql).all()) == int(included)
        # Qualification does not mutate or delete the source/signal population.
        assert connection.exec_driver_sql("SELECT count(*) FROM signals").scalar() >= 1
