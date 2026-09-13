"""Analyze verified S6 artifacts without consulting or writing the database."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flyttsignal.scoring.analysis import analyze_observation


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_captures(directory: Path) -> list[dict[str, Any]]:
    captures = []
    for path in sorted(directory.glob("capture-*.json")):
        capture = read_json(path)
        if path.name != f"capture-{capture['slot']:03d}.json":
            raise ValueError("capture filename and slot disagree")
        captures.append(capture)
    return captures


def write_once(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze_observation(
        read_json(args.directory / "observation.json"),
        load_captures(args.directory),
        now=datetime.now(UTC),
    )
    if args.output:
        write_once(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
