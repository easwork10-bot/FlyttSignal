from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

PILOT_COHORT_VERSION = "pilot-cohort-v1"
PILOT_DIMENSION_SCOPE = "internal-pilot"
StrengthBand = Literal["LOW", "MEDIUM", "HIGH"]
PilotSignalSort = Literal["PRIORITY", "MOVE_WINDOW", "NEWEST"]
PilotReviewStatus = Literal["ALL", "REVIEWED", "UNREVIEWED"]


@dataclass(frozen=True)
class PilotCohortPolicy:
    """Versioned commercial-pilot boundary; persistence and delivery stay outside the domain."""

    city_id: int = 1
    signal_age_days: int = 28
    move_horizon_days: int = 90
    cohort_version: str = PILOT_COHORT_VERSION
    dimension_scope_key: str = PILOT_DIMENSION_SCOPE

    def created_from(self, as_of: date) -> datetime:
        return datetime.combine(as_of - timedelta(days=self.signal_age_days), time.min, UTC)

    def move_horizon_to(self, as_of: date) -> date:
        return as_of + timedelta(days=self.move_horizon_days)


@dataclass(frozen=True)
class PilotSignalFilters:
    """Optional product filters applied inside the immutable pilot cohort boundary."""

    address_query: str | None = None
    review_status: PilotReviewStatus = "ALL"
    strength_band: StrengthBand | None = None
    signal_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    property_type: str | None = None
    min_rooms: Decimal | None = None
    max_rooms: Decimal | None = None
    min_area_m2: Decimal | None = None
    max_area_m2: Decimal | None = None
    center_latitude: Decimal | None = None
    center_longitude: Decimal | None = None
    radius_km: Decimal | None = None

    @property
    def has_radius(self) -> bool:
        return self.radius_km is not None


def strength_band(signal_strength: int) -> StrengthBand:
    if signal_strength >= 60:
        return "HIGH"
    if signal_strength >= 40:
        return "MEDIUM"
    return "LOW"


def signal_age_days(created_at: datetime, as_of: date) -> int:
    return max(0, (as_of - created_at.date()).days)


def days_until_window_start(available_from: date, as_of: date) -> int:
    """Legacy API field; value is now based on advertised available-from timing."""
    return (available_from - as_of).days
