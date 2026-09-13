"""Base score engine interface and common types."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from flyttsignal.domains.signals.snapshots import FeatureSnapshot


@dataclass(frozen=True)
class ScoreInput:
    """Immutable input for score evaluation."""

    snapshot: FeatureSnapshot
    as_of: date


@dataclass(frozen=True)
class ScoreComponent:
    """One component of a score with its contribution."""

    component: str
    points: int
    reason: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ScoreResult:
    """Result of evaluating a dimension for one signal."""

    score: int
    components: tuple[ScoreComponent, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None


class BaseScoreEngine:
    """Abstract base for typed score engines.

    Each engine implements a specific dimension (Signal Strength, Data Confidence, Timing)
    using stable domain code. Version identity lives in registered metadata.
    """

    revision = "signal-engines/2026-09-02"

    def evaluate(self, score_input: ScoreInput) -> ScoreResult:
        """Evaluate the dimension for a given input.

        Args:
            score_input: Feature snapshot and explicit evaluation date.

        Returns:
            ScoreResult with score, components, warnings and optional metadata

        Raises:
            ValueError: If required features are missing or invalid
        """
        raise NotImplementedError("Subclasses must implement evaluate()")
