import uuid
from datetime import UTC, datetime

import pytest

from flyttsignal.db.models import SignalEvidence
from flyttsignal.domains.signals.evidence import supersede_evidence, valid_as_of


def _edge() -> SignalEvidence:
    return SignalEvidence(
        signal_id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        weight=1,
        reason="source event supports signal",
        valid_from=datetime(2026, 9, 8, 7, tzinfo=UTC),
    )


def test_supersession_retains_edge_and_is_idempotent() -> None:
    edge = _edge()
    replacement_event_id = uuid.uuid4()
    at = datetime(2026, 9, 8, 8, tzinfo=UTC)

    assert supersede_evidence(
        edge,
        replacement_event_id=replacement_event_id,
        superseded_at=at,
        reason=" corrected source semantics ",
    )
    assert edge.superseded_at == at
    assert edge.superseded_by_event_id == replacement_event_id
    assert edge.supersession_reason == "corrected source semantics"
    assert not supersede_evidence(
        edge,
        replacement_event_id=replacement_event_id,
        superseded_at=at,
        reason="corrected source semantics",
    )


@pytest.mark.parametrize(
    ("at", "reason", "message"),
    [
        (datetime(2026, 9, 8, 8), "reason", "timezone-aware"),
        (datetime(2026, 9, 8, 8, tzinfo=UTC), " ", "requires a reason"),
    ],
)
def test_supersession_rejects_incomplete_decisions(at, reason, message) -> None:
    with pytest.raises(ValueError, match=message):
        supersede_evidence(
            _edge(),
            replacement_event_id=uuid.uuid4(),
            superseded_at=at,
            reason=reason,
        )


def test_supersession_rejects_same_or_conflicting_replacement() -> None:
    edge = _edge()
    at = datetime(2026, 9, 8, 8, tzinfo=UTC)

    with pytest.raises(ValueError, match="must differ"):
        supersede_evidence(
            edge,
            replacement_event_id=edge.event_id,
            superseded_at=at,
            reason="invalid self replacement",
        )

    supersede_evidence(
        edge,
        replacement_event_id=uuid.uuid4(),
        superseded_at=at,
        reason="first decision",
    )
    with pytest.raises(ValueError, match="different decision"):
        supersede_evidence(
            edge,
            replacement_event_id=uuid.uuid4(),
            superseded_at=at,
            reason="second decision",
        )


def test_valid_as_of_keeps_history_before_supersession() -> None:
    edge = _edge()
    superseded_at = datetime(2026, 9, 8, 9, tzinfo=UTC)
    supersede_evidence(
        edge,
        replacement_event_id=uuid.uuid4(),
        superseded_at=superseded_at,
        reason="corrected source semantics",
    )

    assert not valid_as_of(edge, datetime(2026, 9, 8, 6, 59, tzinfo=UTC))
    assert valid_as_of(edge, edge.valid_from)
    assert valid_as_of(edge, datetime(2026, 9, 8, 8, tzinfo=UTC))
    assert not valid_as_of(edge, superseded_at)


def test_supersession_cannot_predate_evidence() -> None:
    edge = _edge()

    with pytest.raises(ValueError, match="before it became valid"):
        supersede_evidence(
            edge,
            replacement_event_id=uuid.uuid4(),
            superseded_at=datetime(2026, 9, 8, 6, tzinfo=UTC),
            reason="invalid chronology",
        )
