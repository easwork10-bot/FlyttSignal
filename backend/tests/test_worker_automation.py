from types import SimpleNamespace

from flyttsignal.worker.main import (
    configured_listing_lifecycle_policy,
    configured_live_source_states,
)


def test_live_flags_control_all_recurring_rental_sources() -> None:
    settings = SimpleNamespace(
        uppsala_bostadsformedling_live_enabled=True,
        heimstaden_live_enabled=True,
        homeq_public_live_enabled=True,
        hsb_public_live_enabled=False,
    )

    states = configured_live_source_states(settings)

    assert states["uppsala_bostadsformedling_live_rentals"] is True
    assert states["heimstaden_uppsala_rentals"] is True
    assert states["homeq_public_uppsala_live_rentals"] is True
    assert states["homeq_public_uppsala_projects"] is True
    assert states["hsb_public_uppsala_live_rentals"] is False


def test_ubf_listing_lifecycle_is_source_specific_and_off_by_default() -> None:
    settings = SimpleNamespace(
        uppsala_bostadsformedling_listing_lifecycle_enabled=False,
        uppsala_bostadsformedling_listing_lifecycle_grace_runs=2,
    )
    assert (
        configured_listing_lifecycle_policy(settings, "uppsala_bostadsformedling_live_rentals")
        is None
    )

    settings.uppsala_bostadsformedling_listing_lifecycle_enabled = True
    policy = configured_listing_lifecycle_policy(settings, "uppsala_bostadsformedling_live_rentals")
    assert policy is not None
    assert policy.completeness_rule_version == "ubf-public-graphql-v2"
    assert configured_listing_lifecycle_policy(settings, "heimstaden_uppsala_rentals") is None
