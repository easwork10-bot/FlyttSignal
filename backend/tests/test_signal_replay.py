"""Frozen-payload integrity and read-only replay behavior."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from flyttsignal.db.repositories.feature_snapshots import FeatureSnapshotRepository
from flyttsignal.domains.signals.snapshots import FeatureSnapshot
from flyttsignal.scoring.replay import replay_snapshots
from flyttsignal.scoring.scenarios import scenario_catalog

AS_OF = date(2026, 9, 2)


def _snapshots():
    return [scenario.snapshot(as_of_date=AS_OF) for scenario in scenario_catalog()]


def test_every_scenario_payload_roundtrips_without_changing_hash_or_scores() -> None:
    originals = _snapshots()
    restored = [FeatureSnapshot.from_payload(snapshot.payload()) for snapshot in originals]
    for before, after in zip(originals, restored, strict=True):
        assert before.fingerprint() == after.fingerprint()
    assert replay_snapshots(originals) == replay_snapshots(restored)


def test_replay_is_order_independent_and_keeps_all_dimension_results() -> None:
    snapshots = _snapshots()[:3]
    report = replay_snapshots(snapshots)
    assert report == replay_snapshots(list(reversed(snapshots)))
    assert report["population_size"] == 3
    assert len(report["definitions"]) == 3
    for summary in report["summary"]["dimensions"].values():
        assert summary["count"] == 3
        assert sum(summary["score_histogram"].values()) == 3


def test_replay_rejects_empty_duplicate_and_mixed_date_populations() -> None:
    with pytest.raises(ValueError, match="no persisted"):
        replay_snapshots([])
    first, second = _snapshots()[:2]
    with pytest.raises(ValueError, match="one snapshot per signal"):
        replay_snapshots([first, first])
    second_date = FeatureSnapshot(
        second.signal_id, date(2026, 9, 3), second.features, second.schema_revision
    )
    with pytest.raises(ValueError, match="one as_of"):
        replay_snapshots([first, second_date])


def _stored(snapshot):
    return SimpleNamespace(
        id=UUID("955b2604-3b55-4a86-9de5-86147a08e576"),
        signal_id=snapshot.signal_id,
        as_of_date=snapshot.as_of_date,
        feature_schema_revision=snapshot.schema_revision,
        payload=snapshot.payload(),
        payload_hash=snapshot.fingerprint(),
        captured_at=datetime(2026, 9, 2, 14, tzinfo=UTC),
    )


def _repository(rows):
    # Deliberately supplies no add/commit operation: historical loading must only read.
    session = SimpleNamespace(scalars=lambda query: iter(rows))
    return FeatureSnapshotRepository(session)


def test_historical_loader_checks_hash_and_preserves_persisted_identity() -> None:
    row = _stored(_snapshots()[0])
    loaded = _repository([row]).historical(city_id=1, as_of_date=AS_OF)
    assert loaded[0].id == row.id
    assert loaded[0].snapshot.fingerprint() == row.payload_hash
    row.payload_hash = "0" * 64
    with pytest.raises(ValueError, match="hash does not match"):
        _repository([row]).historical(city_id=1, as_of_date=AS_OF)


def test_historical_loader_rejects_ambiguous_same_day_versions() -> None:
    row = _stored(_snapshots()[0])
    with pytest.raises(ValueError, match="capture manifest"):
        _repository([row, row]).historical(city_id=1, as_of_date=AS_OF)


@pytest.mark.parametrize("field", ["signal_id", "as_of_date", "feature_schema_revision"])
def test_historical_loader_rejects_metadata_payload_disagreement(field: str) -> None:
    row = _stored(_snapshots()[0])
    setattr(row, field, "incorrect")
    with pytest.raises(ValueError, match="different"):
        _repository([row]).historical(city_id=1, as_of_date=AS_OF)
