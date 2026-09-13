"""Capture a bounded, fixed-definition shadow observation without database writes."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from flyttsignal.db.models import Source
from flyttsignal.db.repositories.feature_snapshots import FeatureSnapshotRepository
from flyttsignal.db.session import SessionLocal
from flyttsignal.scoring.observation import (
    capture_slot,
    create_plan,
    observation_status,
    seal,
    validate_capture,
)
from flyttsignal.scoring.replay import replay_snapshots


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: dict[str, Any]) -> None:
    """Never overwrite a plan/capture; incomplete files fail integrity checks on retry."""

    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def build_capture(plan: dict[str, Any], now: datetime) -> dict[str, Any]:
    slot = capture_slot(plan, now)
    if slot is None:
        raise ValueError("capture is outside the observation window")
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        snapshots = FeatureSnapshotRepository(session).build_current(
            city_id=plan["city_id"],
            as_of_date=now.astimezone(ZoneInfo("Europe/Stockholm")).date(),
            captured_at=now,
        )
        report = replay_snapshots(snapshots)
        keys: set[str] = set()
        for snapshot in snapshots:
            channel = snapshot.features["publisher_channel"].value
            if isinstance(channel, str):
                keys.add(channel)
            elif isinstance(channel, list):
                keys.update(channel)
        source_health = []
        for source in session.scalars(
            select(Source).where(Source.key.in_(keys)).order_by(Source.key)
        ):
            age = (
                (now - source.last_success_at).total_seconds() / 3600
                if source.last_success_at
                else None
            )
            source_health.append(
                {
                    "key": source.key,
                    "enabled": source.enabled,
                    "status": source.status,
                    "last_success_at": source.last_success_at.isoformat()
                    if source.last_success_at
                    else None,
                    "poll_interval_minutes": source.poll_interval_minutes,
                    "success_age_hours": round(age, 3) if age is not None else None,
                    "stale": age is None or age > source.poll_interval_minutes / 30,
                }
            )
    capture = seal(
        {
            "plan_hash": plan["plan_hash"],
            "slot": slot,
            "captured_at": now.isoformat(),
            "snapshots": [snapshot.payload() for snapshot in snapshots],
            "replay": report,
            "source_health": source_health,
        },
        "capture_hash",
    )
    validate_capture(plan, capture)
    return capture


def load_captures(directory: Path) -> list[dict[str, Any]]:
    captures = []
    for path in sorted(directory.glob("capture-*.json")):
        capture = read_json(path)
        if path.name != f"capture-{capture['slot']:03d}.json":
            raise ValueError("capture filename and slot disagree")
        captures.append(capture)
    return captures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "capture", "status"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--city-id", type=int, default=1)
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument("--interval-hours", type=int, default=3)
    args = parser.parse_args()
    now = datetime.now(UTC)
    plan_path = args.directory / "observation.json"

    if args.action == "start":
        if not args.reference:
            parser.error("start requires --reference to pin the approved candidate report")
        if args.directory.exists() and any(args.directory.iterdir()):
            raise ValueError("start requires a new or empty observation directory")
        plan = create_plan(
            read_json(args.reference),
            now=now,
            city_id=args.city_id,
            hours=args.hours,
            interval_hours=args.interval_hours,
        )
        capture = build_capture(plan, now)
        args.directory.mkdir(parents=True, exist_ok=True)
        write_once(plan_path, plan)
        write_once(args.directory / "capture-000.json", capture)
        action = "CAPTURED"
    else:
        plan = read_json(plan_path)
        # Check all previous artifacts before deciding whether a new capture is allowed.
        observation_status(plan, load_captures(args.directory), now)
        slot = capture_slot(plan, now)
        action = "STATUS"
        if args.action == "capture" and slot is not None:
            path = args.directory / f"capture-{slot:03d}.json"
            action = "ALREADY_CAPTURED"
            if not path.exists():
                capture = build_capture(plan, now)
                try:
                    write_once(path, capture)
                    action = "CAPTURED"
                except FileExistsError:
                    # Another invocation won this slot; the status check verifies its artifact.
                    pass
    status = observation_status(plan, load_captures(args.directory), now)
    print(json.dumps({"action": action, **status}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
