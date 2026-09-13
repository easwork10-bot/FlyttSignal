import asyncio

from scripts.load_demo_data import main


def test_demo_data_is_explicit_and_dry_run_by_default() -> None:
    result = asyncio.run(main(dataset_names=("primary", "partner"), apply=False))

    assert result == {
        "fake_uppsala_rentals": 10,
        "fake_uppsala_partner": 5,
    }
