from dataclasses import dataclass
from decimal import Decimal
from typing import Any

CLASSIFICATION_RULE_VERSION = "classification-v1"

CATEGORY_TAGS = {
    "studentboende": "STUDENT_HOUSING",
    "senior": "SENIOR_HOUSING",
    "ungdom": "YOUTH_HOUSING",
    "korttidskontrakt": "SHORT_TERM",
    "tillsvidarekontrakt": "PERMANENT_CONTRACT",
    "vanligt boende": "STANDARD_HOUSING",
    "lägenhet": "APARTMENT",
    "rum": "ROOM",
    "hus": "HOUSE",
}


@dataclass(frozen=True)
class Classification:
    tag: str
    confidence: Decimal
    reason: str
    evidence: dict[str, Any]
    rule_version: str = CLASSIFICATION_RULE_VERSION


def resolve_construction_state(
    *,
    observed: bool | None,
    previous: bool | None,
    observation_complete: bool = False,
) -> bool | None:
    """Retain positives and repair legacy false when a tri-state observation is complete."""

    if observed is not None:
        return observed
    if observation_complete and previous is False:
        return None
    return previous


def classify_listing(
    *, new_construction: bool | None, categories: list[str]
) -> tuple[Classification, ...]:
    classifications: dict[str, Classification] = {}
    if new_construction:
        classifications["NEW_CONSTRUCTION"] = Classification(
            tag="NEW_CONSTRUCTION",
            confidence=Decimal("1.000"),
            reason="explicit_normalized_field",
            evidence={"field": "new_construction", "value": True},
        )
    for category in categories:
        normalized = " ".join(str(category).strip().casefold().split())
        tag = CATEGORY_TAGS.get(normalized)
        if tag is not None:
            classifications[tag] = Classification(
                tag=tag,
                confidence=Decimal("1.000"),
                reason="explicit_public_category",
                evidence={"field": "categories", "value": str(category).strip()},
            )
    if not classifications:
        classifications["UNKNOWN"] = Classification(
            tag="UNKNOWN",
            confidence=Decimal("0.000"),
            reason="no_explicit_classification_evidence",
            evidence={"recognized_categories": []},
        )
    return tuple(classifications.values())
