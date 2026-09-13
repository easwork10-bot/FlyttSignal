import enum


class PilotFeedbackVerdict(enum.StrEnum):
    USEFUL = "USEFUL"
    MAYBE = "MAYBE"
    NOT_USEFUL = "NOT_USEFUL"


class PilotFeedbackReason(enum.StrEnum):
    GOOD_OPPORTUNITY = "GOOD_OPPORTUNITY"
    TOO_EARLY = "TOO_EARLY"
    TOO_LATE = "TOO_LATE"
    WRONG_PROPERTY = "WRONG_PROPERTY"
    WEAK_SIGNAL = "WEAK_SIGNAL"
    DUPLICATE = "DUPLICATE"
    OUTSIDE_SERVICE_AREA = "OUTSIDE_SERVICE_AREA"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


ALLOWED_REASONS: dict[PilotFeedbackVerdict, frozenset[PilotFeedbackReason]] = {
    PilotFeedbackVerdict.USEFUL: frozenset({PilotFeedbackReason.GOOD_OPPORTUNITY}),
    PilotFeedbackVerdict.MAYBE: frozenset(
        {
            PilotFeedbackReason.TOO_EARLY,
            PilotFeedbackReason.TOO_LATE,
            PilotFeedbackReason.INSUFFICIENT_CONTEXT,
        }
    ),
    PilotFeedbackVerdict.NOT_USEFUL: frozenset(
        reason
        for reason in PilotFeedbackReason
        if reason is not PilotFeedbackReason.GOOD_OPPORTUNITY
    ),
}


def reason_is_valid(verdict: PilotFeedbackVerdict, reason: PilotFeedbackReason) -> bool:
    return reason in ALLOWED_REASONS[verdict]
