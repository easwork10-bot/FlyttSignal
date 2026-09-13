from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from flyttsignal.domains.signals.timing import ResolvedTimingFact


class TimingReadMode(StrEnum):
    CURRENT = "CURRENT"
    AS_OF = "AS_OF"


@dataclass(frozen=True)
class ResolvedSignalTiming:
    """Typed timing facts and the temporal boundary used to resolve them."""

    primary: ResolvedTimingFact
    facts: tuple[ResolvedTimingFact, ...]
    mode: TimingReadMode
    as_of: datetime | None
    warnings: tuple[str, ...] = ()
