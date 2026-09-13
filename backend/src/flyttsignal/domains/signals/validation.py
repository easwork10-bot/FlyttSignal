import hashlib
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date

VALIDATION_RULE_VERSION = "validation-v2"
SPECIAL_TAGS = frozenset(
    {
        "NEW_CONSTRUCTION",
        "STUDENT_HOUSING",
        "UNKNOWN",
        "SHORT_TERM",
        "SENIOR_HOUSING",
        "YOUTH_HOUSING",
    }
)
ALLOWED_VERDICTS = frozenset({"GOOD", "QUESTIONABLE", "BAD"})
ALLOWED_ISSUE_CODES = frozenset(
    {
        "WRONG_CLASSIFICATION",
        "WEAK_INFERENCE",
        "BAD_DATE",
        "BAD_MATCH",
        "DUPLICATE",
        "INSUFFICIENT_EVIDENCE",
        "SCORE_TOO_HIGH",
        "SCORE_TOO_LOW",
        "STALE_NORMALIZED_PROPERTY",
        "OTHER",
    }
)


@dataclass(frozen=True)
class ValidationCandidate:
    signal_id: uuid.UUID
    score_run_id: uuid.UUID
    score_as_of_date: date
    definition_set_hash: str
    signal_strength: int
    data_confidence: int
    timing: int
    listing_ids: tuple[uuid.UUID, ...]
    property_ids: tuple[uuid.UUID, ...]
    source_keys: tuple[str, ...]
    provider_keys: tuple[str, ...]
    classification_tags: tuple[str, ...]
    missing_available_from: bool
    cross_source_property: bool

    @property
    def cross_source(self) -> bool:
        return self.cross_source_property


@dataclass(frozen=True)
class SelectedValidation:
    candidate: ValidationCandidate
    strength_stratum: str
    inclusion_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ValidationSelection:
    selected: tuple[SelectedValidation, ...]
    manifest: dict


def strength_stratum(signal_strength: int) -> str:
    if signal_strength >= 60:
        return "HIGH"
    if signal_strength >= 40:
        return "MEDIUM"
    return "LOW"


def _allocate_quotas(counts: Counter, target_size: int) -> dict[str, int]:
    strata = ("LOW", "HIGH", "MEDIUM")
    base, remainder = divmod(target_size, len(strata))
    quotas = {
        stratum: min(counts[stratum], base + (index < remainder))
        for index, stratum in enumerate(strata)
    }
    remaining = target_size - sum(quotas.values())
    redistributable = ("HIGH", "MEDIUM", "LOW")
    while remaining:
        progressed = False
        for stratum in redistributable:
            if quotas[stratum] < counts[stratum]:
                quotas[stratum] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
        if not progressed:
            raise ValueError("target_size exceeds candidate population")
    return quotas


def _tokens(candidate: ValidationCandidate) -> dict[str, int]:
    tokens = {f"source:{key}": 3 for key in candidate.source_keys}
    tokens.update({f"provider:{key}": 1 for key in candidate.provider_keys})
    tokens.update({f"tag:{tag}": 4 for tag in candidate.classification_tags if tag in SPECIAL_TAGS})
    if candidate.missing_available_from:
        tokens["risk:missing_available_from"] = 6
    if candidate.cross_source:
        tokens["risk:cross_source"] = 6
    return tokens


def _stable_rank(candidate: ValidationCandidate, seed: str) -> str:
    return hashlib.sha256(f"{seed}:{candidate.signal_id}".encode()).hexdigest()


def select_validation_sample(
    candidates: list[ValidationCandidate], *, target_size: int = 60, seed: str
) -> ValidationSelection:
    if target_size <= 0:
        raise ValueError("target_size must be positive")
    unique = {candidate.signal_id: candidate for candidate in candidates}
    if len(unique) != len(candidates):
        raise ValueError("candidate signal IDs must be unique")
    if len(candidates) < target_size:
        raise ValueError("target_size exceeds candidate population")

    activation_sets = {
        (candidate.score_run_id, candidate.score_as_of_date, candidate.definition_set_hash)
        for candidate in candidates
    }
    if len(activation_sets) != 1:
        raise ValueError("candidates must share one activated dimension run")
    populations = Counter(strength_stratum(candidate.signal_strength) for candidate in candidates)
    quotas = _allocate_quotas(populations, target_size)
    coverage: Counter[str] = Counter()
    selected: list[SelectedValidation] = []
    selected_ids = set()

    for stratum in ("LOW", "HIGH", "MEDIUM"):
        pool = [
            candidate
            for candidate in candidates
            if strength_stratum(candidate.signal_strength) == stratum
        ]
        for _ in range(quotas[stratum]):
            remaining = [item for item in pool if item.signal_id not in selected_ids]

            def priority(item: ValidationCandidate) -> tuple[float, str]:
                gain = sum(
                    weight / (1 + coverage[token]) for token, weight in _tokens(item).items()
                )
                return (-gain, _stable_rank(item, seed))

            chosen = min(remaining, key=priority)
            selected_ids.add(chosen.signal_id)
            coverage.update(_tokens(chosen).keys())
            reasons = [f"SIGNAL_STRENGTH_{stratum}"]
            reasons.extend(
                f"TAG_{tag}" for tag in chosen.classification_tags if tag in SPECIAL_TAGS
            )
            if chosen.missing_available_from:
                reasons.append("MISSING_AVAILABLE_FROM")
            if chosen.cross_source:
                reasons.append("CROSS_SOURCE_PROPERTY")
            selected.append(SelectedValidation(chosen, stratum, tuple(sorted(set(reasons)))))

    selected.sort(key=lambda item: (item.strength_stratum, str(item.candidate.signal_id)))
    actual_strata = Counter(item.strength_stratum for item in selected)
    selected_tags = Counter(tag for item in selected for tag in item.candidate.classification_tags)
    selected_sources = Counter(key for item in selected for key in item.candidate.source_keys)
    manifest = {
        "rule_version": VALIDATION_RULE_VERSION,
        "dimension_scope_key": "internal-pilot",
        "score_run_id": str(candidates[0].score_run_id),
        "score_as_of_date": candidates[0].score_as_of_date.isoformat(),
        "definition_set_hash": candidates[0].definition_set_hash,
        "seed": seed,
        "target_size": target_size,
        "population_size": len(candidates),
        "population_strata": dict(sorted(populations.items())),
        "target_strata": dict(sorted(quotas.items())),
        "selected_strata": dict(sorted(actual_strata.items())),
        "selected_special_tags": {
            key: selected_tags[key] for key in sorted(SPECIAL_TAGS) if selected_tags[key]
        },
        "selected_sources": dict(sorted(selected_sources.items())),
        "missing_available_from": sum(item.candidate.missing_available_from for item in selected),
        "cross_source": sum(item.candidate.cross_source for item in selected),
    }
    return ValidationSelection(tuple(selected), manifest)


def validate_review(verdict: str, issue_codes: list[str]) -> tuple[str, tuple[str, ...]]:
    normalized_verdict = verdict.strip().upper()
    if normalized_verdict not in ALLOWED_VERDICTS:
        raise ValueError(f"invalid verdict: {verdict}")
    normalized_codes = tuple(sorted({code.strip().upper() for code in issue_codes if code.strip()}))
    unknown = set(normalized_codes) - ALLOWED_ISSUE_CODES
    if unknown:
        raise ValueError(f"invalid issue codes: {', '.join(sorted(unknown))}")
    if normalized_verdict == "GOOD" and normalized_codes:
        raise ValueError("GOOD reviews cannot contain issue codes")
    if normalized_verdict != "GOOD" and not normalized_codes:
        raise ValueError("QUESTIONABLE and BAD reviews require at least one issue code")
    return normalized_verdict, normalized_codes
