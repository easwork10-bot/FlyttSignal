from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BenchmarkObservationInput:
    dataset_key: str
    metric_key: str
    municipality_code: str
    period: str
    value: Decimal | None
    unit: str
    dimensions: dict[str, str]
    source_updated_at: datetime | None
