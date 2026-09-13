from datetime import UTC, date, datetime
from uuid import UUID

import pytest

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
    assert first.fingerprint() != FeatureSnapshot(
        SIGNAL_ID, date(2026, 9, 2), changed
    ).fingerprint()


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
    assert snapshot.payload()["features"]["first_seen_at"]["value"] == (
        "2026-09-02T08:00:00+00:00"
    )


def test_current_state_capture_cannot_be_backdated() -> None:
    repository = FeatureSnapshotRepository(object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="historical replay"):
        repository.build_current(
            city_id=1,
            as_of_date=date(2026, 9, 1),
            captured_at=datetime(2026, 9, 2, 8, tzinfo=UTC),
        )
