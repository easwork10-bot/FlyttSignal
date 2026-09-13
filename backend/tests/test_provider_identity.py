from flyttsignal.domains.housing_providers.identity import canonical_provider_key


def test_provider_aliases_are_shared_across_publisher_channels() -> None:
    assert canonical_provider_key("Fastighets AB Balder", "homeq-landlord", 3) == "balder"
    assert canonical_provider_key("Klövern", "ubf-landlord", 200054007458) == "klovern"
    assert canonical_provider_key("Klövern", "homeq-landlord", 1028) == "klovern"
    assert canonical_provider_key("Juli Living", "ubf-landlord", 1) == "juli-living"
    assert canonical_provider_key("Juli Living", "homeq-landlord", 568) == "juli-living"
    assert canonical_provider_key("Sveaviken PM", "ubf-landlord", 1) == "sveaviken-pm"


def test_unknown_provider_retains_publisher_stable_id() -> None:
    assert canonical_provider_key("Example AB", "homeq-landlord", 42) == "homeq-landlord-42"
