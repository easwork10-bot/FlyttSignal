from flyttsignal.domains.events.models import EventType


def event_type_for(*, new_construction: bool | None) -> EventType:
    if new_construction:
        return EventType.NEW_BUILD_MOVE_IN
    return EventType.RENTAL_LISTED
