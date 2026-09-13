"""Preview or apply the narrow property-provenance remediation."""

import argparse
import json

from flyttsignal.db.session import SessionLocal
from flyttsignal.property_provenance.service import remediate_property_provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source", help="Restrict remediation to one exact source key.")
    parser.add_argument("--active-only", action="store_true")
    parser.add_argument("--summary", action="store_true", help="Omit individual actions.")
    args = parser.parse_args()

    with SessionLocal() as session:
        result = remediate_property_provenance(
            session,
            apply=args.apply,
            source_key=args.source,
            active_only=args.active_only,
        )
    report = result.as_dict()
    if args.summary:
        report.pop("actions")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
