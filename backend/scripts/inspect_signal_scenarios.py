"""Print the deterministic signal-engine scenario catalog summary."""

import argparse
import json
from collections import Counter
from datetime import date

from flyttsignal.scoring.scenarios import scenario_catalog, scenario_catalog_fingerprint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    catalog = scenario_catalog()
    families = Counter(scenario.family.value for scenario in catalog)
    invariants = Counter(
        invariant for scenario in catalog for invariant in scenario.invariants
    )
    print(
        json.dumps(
            {
                "as_of_date": args.as_of.isoformat(),
                "catalog_fingerprint": scenario_catalog_fingerprint(as_of_date=args.as_of),
                "families": dict(sorted(families.items())),
                "invariants": dict(sorted(invariants.items())),
                "scenario_count": len(catalog),
                "scenarios": [scenario.key for scenario in catalog],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
