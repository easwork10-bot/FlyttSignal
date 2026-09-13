from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ListingStatus = Literal["ACTIVE", "REMOVAL_CANDIDATE", "REMOVED"]


@dataclass(frozen=True)
class ListingLifecyclePolicy:
    source_key: str
    completeness_rule_version: str
    grace_runs: int = 2


@dataclass(frozen=True)
class ListingLifecycleResult:
    applied: bool
    candidates: int = 0
    removed: int = 0
    removed_listing_ids: tuple[UUID, ...] = ()
    reasons: tuple[str, ...] = ()


def listing_status_after_miss(miss_count: int, configured_grace_runs: int) -> ListingStatus:
    """Fail closed: no policy can remove a listing after fewer than two misses."""

    return "REMOVED" if miss_count >= max(2, configured_grace_runs) else "REMOVAL_CANDIDATE"
