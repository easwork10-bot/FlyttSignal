from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PropertyIdentity:
    unit_identifier: str | None
    rooms: Decimal | None
    area_m2: Decimal | None
    new_construction: bool | None

    def as_dict(self) -> dict[str, str | bool | None]:
        return {
            "unit_identifier": self.unit_identifier,
            "rooms": str(self.rooms) if self.rooms is not None else None,
            "area_m2": str(self.area_m2) if self.area_m2 is not None else None,
            "new_construction": self.new_construction,
        }
