from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from flyttsignal.property_provenance.verification import (
    VerificationMode,
    VerificationStatus,
    evidence_applies,
    verify_projection,
)

AS_OF = datetime(2026, 8, 30, 8, 47, tzinfo=UTC)


def test_historical_false_is_not_compared_to_current_true() -> None:
    result = verify_projection(
        mode=VerificationMode.AS_OF,
        current_expected=True,
        current_actual=True,
        historical_expected=False,
        historical_actual=False,
    )
    assert result.status is VerificationStatus.PASS


def test_historical_false_is_not_compared_to_current_unknown() -> None:
    result = verify_projection(
        mode=VerificationMode.AS_OF,
        current_expected=None,
        current_actual=None,
        historical_expected=False,
        historical_actual=False,
    )
    assert result.status is VerificationStatus.PASS


def test_evidence_superseded_later_remains_valid_as_of() -> None:
    evidence = SimpleNamespace(
        event_id=uuid4(),
        valid_from=AS_OF - timedelta(days=1),
        superseded_at=AS_OF + timedelta(days=1),
    )
    assert evidence_applies(evidence, mode=VerificationMode.AS_OF, as_of=AS_OF)
    assert not evidence_applies(evidence, mode=VerificationMode.CURRENT, as_of=AS_OF)


def test_unavailable_historical_identity_is_unknown() -> None:
    result = verify_projection(
        mode=VerificationMode.AS_OF,
        current_expected=True,
        current_actual=False,
    )
    assert result.status is VerificationStatus.UNKNOWN
    assert result.reason == "historical_property_identity_not_captured"


def test_current_state_actual_mismatch_fails() -> None:
    result = verify_projection(
        mode=VerificationMode.CURRENT,
        current_expected=True,
        current_actual=False,
    )
    assert result.status is VerificationStatus.FAIL
