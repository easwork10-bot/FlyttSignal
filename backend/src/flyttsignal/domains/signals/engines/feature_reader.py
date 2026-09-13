"""State-aware access to immutable signal feature snapshots."""

from __future__ import annotations

from typing import Any

from flyttsignal.domains.signals.snapshots import FeatureSnapshot, FeatureValueState


class FeatureReader:
    """Read features without collapsing missing, unavailable, or conflicting states."""

    def __init__(self, snapshot: FeatureSnapshot, warnings: list[str]):
        self._features = snapshot.features
        self._warnings = warnings

    def value(self, name: str) -> Any | None:
        feature = self._features[name]
        if feature.state is FeatureValueState.PRESENT:
            return feature.value
        self._warnings.append(
            f"{name} is {feature.state.value.lower()}: {feature.reason or 'no reason supplied'}"
        )
        return None

    def boolean(self, name: str) -> bool | None:
        value = self.value(name)
        if value is None:
            return None
        if not isinstance(value, bool):
            self._warnings.append(f"{name} is not a boolean")
            return None
        return value

    def integer(self, name: str) -> int | None:
        value = self.value(name)
        if value is None:
            return None
        if isinstance(value, bool):
            self._warnings.append(f"{name} is not an integer")
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            self._warnings.append(f"{name} is not an integer")
            return None

    def number(self, name: str) -> float | None:
        value = self.value(name)
        if value is None:
            return None
        if isinstance(value, bool):
            self._warnings.append(f"{name} is not a number")
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            self._warnings.append(f"{name} is not a number")
            return None
