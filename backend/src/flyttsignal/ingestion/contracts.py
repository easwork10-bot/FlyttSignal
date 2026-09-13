from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, overload
from uuid import UUID

from flyttsignal.benchmarking.service import BenchmarkObservationInput
from flyttsignal.domains.developments.models import RentalDevelopment
from flyttsignal.enrichment.service import AddressEnrichmentInput
from flyttsignal.normalization.service import NormalizedItem
from flyttsignal.spatial.service import SpatialFeatureInput

DEFAULT_COMPLETENESS_RULE_VERSION = "snapshot-integrity-v1"


@dataclass(frozen=True)
class AddressEnrichmentTarget:
    address_id: UUID
    address: str
    municipality_code: str


@dataclass(frozen=True)
class SnapshotEvidence:
    """Facts observed during one fetch; unknown facts stay None."""

    requests_attempted: int | None = None
    requests_succeeded: int | None = None
    requests_failed: int | None = None
    pages_expected: int | None = None
    pages_received: int | None = None
    items_reported: int | None = None
    items_received: int | None = None
    pagination_complete: bool | None = None
    hit_result_limit: bool | None = None
    inventory_scope_complete: bool | None = None
    rule_version: str = DEFAULT_COMPLETENESS_RULE_VERSION
    reasons: tuple[str, ...] = ()
    evidence: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class FetchResult[PayloadT]:
    """Typed result for one source fetch, including per-run integrity facts."""

    items: list[PayloadT]
    snapshot: SnapshotEvidence

    def __iter__(self) -> Iterator[PayloadT]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @overload
    def __getitem__(self, index: int) -> PayloadT: ...

    @overload
    def __getitem__(self, index: slice) -> list[PayloadT]: ...

    def __getitem__(self, index: int | slice) -> PayloadT | list[PayloadT]:
        return self.items[index]


def complete_fixture_result[PayloadT](items: list[PayloadT]) -> FetchResult[PayloadT]:
    """A repository file is a complete snapshot of that deterministic fixture only."""

    count = len(items)
    return FetchResult(
        items,
        SnapshotEvidence(
            requests_attempted=1,
            requests_succeeded=1,
            requests_failed=0,
            pages_expected=1,
            pages_received=1,
            items_reported=count,
            items_received=count,
            pagination_complete=True,
            hit_result_limit=False,
            inventory_scope_complete=True,
            rule_version="repository-fixture-v1",
            reasons=("complete_repository_fixture",),
            evidence={"transport": "repository_file", "scope": "fixture_only"},
        ),
    )


class SourceAdapter(ABC):
    source_key: str

    @abstractmethod
    async def fetch(self) -> FetchResult[dict[str, Any]]: ...

    def parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    @abstractmethod
    def normalize(self, item: dict[str, Any]) -> NormalizedItem: ...


class BenchmarkAdapter(ABC):
    """Aggregate context that must never create property events."""

    source_key: str

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]: ...

    def parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    @abstractmethod
    def normalize(self, item: dict[str, Any]) -> list[BenchmarkObservationInput]: ...


class AddressEnrichmentAdapter(ABC):
    """Canonical address data that must not create events or signals."""

    source_key: str
    target_limit: int = 25

    @abstractmethod
    async def fetch(self, targets: list[AddressEnrichmentTarget]) -> list[dict[str, Any]]: ...

    def parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    @abstractmethod
    def normalize(self, item: dict[str, Any]) -> AddressEnrichmentInput: ...


class SpatialFeatureAdapter(ABC):
    """Score-neutral geographic features."""

    source_key: str

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]: ...

    def parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    @abstractmethod
    def normalize(self, item: dict[str, Any]) -> SpatialFeatureInput: ...


class RentalDevelopmentAdapter(ABC):
    """Development metadata is inventory context, never a synthetic rental event."""

    source_key: str

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]: ...

    def parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    @abstractmethod
    def normalize(self, item: dict[str, Any]) -> RentalDevelopment: ...
