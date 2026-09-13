"""Score engines for Signal Strength, Data Confidence and Timing dimensions.

Each engine is a typed domain policy, not a generic JSON rules language.
Reproducibility and versioning live in registered metadata, not in filenames.
"""

from flyttsignal.domains.signals.engines.base import BaseScoreEngine, ScoreInput, ScoreResult
from flyttsignal.domains.signals.engines.data_confidence import (
    DataConfidenceEngine,
    DataConfidenceParameters,
    calculate_data_confidence,
)
from flyttsignal.domains.signals.engines.metadata import (
    DefinitionMetadata,
    ScoreDefinitionStatus,
    ScoreDimension,
)
from flyttsignal.domains.signals.engines.signal_strength import (
    SignalStrengthEngine,
    SignalStrengthParameters,
    calculate_signal_strength,
)
from flyttsignal.domains.signals.engines.timing import (
    TimingEngine,
    TimingParameters,
    calculate_timing,
)

__all__ = [
    "BaseScoreEngine",
    "ScoreResult",
    "ScoreInput",
    "DefinitionMetadata",
    "ScoreDimension",
    "ScoreDefinitionStatus",
    "SignalStrengthEngine",
    "SignalStrengthParameters",
    "calculate_signal_strength",
    "DataConfidenceEngine",
    "DataConfidenceParameters",
    "calculate_data_confidence",
    "TimingEngine",
    "TimingParameters",
    "calculate_timing",
]
