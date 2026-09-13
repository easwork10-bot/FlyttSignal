from dataclasses import dataclass

OUTCOME_RULE_VERSION = "outcome-v1"


@dataclass(frozen=True)
class OutcomeDefinition:
    subject: str
    verification_level: str


OUTCOME_DEFINITIONS = {
    "LISTING_REMOVED": OutcomeDefinition("LISTING", "OBSERVED"),
    "LISTING_RELISTED": OutcomeDefinition("LISTING", "OBSERVED"),
    "AVAILABLE_DATE_CHANGED": OutcomeDefinition("LISTING", "OBSERVED"),
    "CROSS_SOURCE_CONFIRMED": OutcomeDefinition("SIGNAL", "OBSERVED"),
    "UNKNOWN": OutcomeDefinition("SIGNAL", "OBSERVED"),
    "CONFIRMED_MOVE": OutcomeDefinition("HOUSEHOLD_MOVE", "CONFIRMED"),
}
