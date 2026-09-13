import enum
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


class SourceType(enum.StrEnum):
    PUBLIC_API = "PUBLIC_API"
    OPEN_DATA = "OPEN_DATA"
    PUBLIC_WEB = "PUBLIC_WEB"
    PARTNER_API = "PARTNER_API"
    FILE = "FILE"
    FAKE = "FAKE"


class Scope(enum.StrEnum):
    LOCAL = "LOCAL"
    REGIONAL = "REGIONAL"
    NATIONAL = "NATIONAL"


class RunStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class RunTrigger(enum.StrEnum):
    UNKNOWN = "UNKNOWN"
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def now():
    return mapped_column(DateTime(timezone=True), server_default=func.now())
