"""Report registry coverage for one verified observation capture; no database access."""

import argparse
import json
from collections import Counter
from pathlib import Path

from flyttsignal.domains.signals.features import FEATURE_REGISTRY
from flyttsignal.scoring.observation import validate_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    plan = json.loads(args.capture.with_name("observation.json").read_text(encoding="utf-8"))
    validate_capture(plan, capture)
    snapshots = capture["snapshots"]
    expected = {spec.name for spec in FEATURE_REGISTRY}
    if any(set(item["features"]) != expected for item in snapshots):
        raise ValueError("capture and current registry differ")
    groups = {"ALL": snapshots}
    for item in snapshots:
        channel = item["features"]["publisher_channel"]
        # Conflicting provenance remains a separate group, never credited to one source.
        key = json.dumps(channel, sort_keys=True, ensure_ascii=False)
        groups.setdefault(key, []).append(item)
    result = {
        "capture_file": args.capture.name,
        "captured_at": capture["captured_at"],
        "capture_hash": capture["capture_hash"],
        "population_size": len(snapshots),
        "feature_count": len(FEATURE_REGISTRY),
        "groups": {},
    }
    for key, items in groups.items():
        features = {}
        for spec in FEATURE_REGISTRY:
            values = [item["features"][spec.name] for item in items]
            states = Counter(value["state"] for value in values)
            features[spec.name] = {
                "source": spec.source,
                "definition": spec.definition,
                "type": spec.value_type,
                "allowed_values": list(spec.allowed_values),
                "availability": spec.availability.value,
                "affects": sorted(spec.affects),
                "prohibits": sorted(spec.prohibits),
                "uses": sorted(spec.uses),
                "missing_semantics": spec.missing_semantics,
                "states": {
                    state: {
                        "count": states[state],
                        "percent": round(100 * states[state] / len(items), 3),
                    }
                    for state in ("PRESENT", "MISSING", "NOT_AVAILABLE", "CONFLICTING")
                },
                "present_false": sum(
                    v["state"] == "PRESENT" and v.get("value") is False for v in values
                ),
                "reasons": dict(
                    sorted(
                        Counter(
                            value.get("reason", "unspecified")
                            for value in values
                            if value["state"] != "PRESENT"
                        ).items()
                    )
                ),
            }
        result["groups"][key] = {"population_size": len(items), "features": features}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: value for key, value in result.items() if key != "groups"}))


if __name__ == "__main__":
    main()
