from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from flyttsignal.db.session import get_db

Db = Annotated[Session, Depends(get_db)]
