from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

LEAD_TIME_METRIC = "LEAD_TIME_DAYS"
LEAD_TIME_RULE_VERSION = "lead-time-v1"
LEAD_TIME_TIMEZONE = "Europe/Stockholm"


@dataclass(frozen=True)
class Measurement:
    metric: str
    value: Decimal | None
    unit: str
    status: str
    rule_version: str
    inputs: dict[str, Any]


def measure_lead_time(
    *, first_seen_at: datetime | None, available_from: date | None
) -> Measurement:
    missing = [
        field
        for field, value in (
            ("first_seen_at", first_seen_at),
            ("available_from", available_from),
        )
        if value is None
    ]
    if missing:
        return Measurement(
            metric=LEAD_TIME_METRIC,
            value=None,
            unit="days",
            status="MISSING_INPUT",
            rule_version=LEAD_TIME_RULE_VERSION,
            inputs={"missing": missing, "timezone": LEAD_TIME_TIMEZONE},
        )
    if first_seen_at.tzinfo is None:
        return Measurement(
            metric=LEAD_TIME_METRIC,
            value=None,
            unit="days",
            status="INVALID_INPUT",
            rule_version=LEAD_TIME_RULE_VERSION,
            inputs={"invalid": ["first_seen_at_timezone"], "timezone": LEAD_TIME_TIMEZONE},
        )

    first_seen_date = first_seen_at.astimezone(ZoneInfo(LEAD_TIME_TIMEZONE)).date()
    days = (available_from - first_seen_date).days
    return Measurement(
        metric=LEAD_TIME_METRIC,
        value=Decimal(days),
        unit="days",
        status="MEASURED",
        rule_version=LEAD_TIME_RULE_VERSION,
        inputs={
            "first_seen_at": first_seen_at.isoformat(),
            "first_seen_local_date": first_seen_date.isoformat(),
            "available_from": available_from.isoformat(),
            "timezone": LEAD_TIME_TIMEZONE,
            "formula": "available_from - local_date(first_seen_at)",
            "late_observation": days < 0,
        },
    )
