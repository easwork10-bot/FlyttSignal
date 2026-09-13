from pydantic import BaseModel, ConfigDict


class CityOut(BaseModel):
    id: int
    name: str
    municipality_code: str
    enabled: bool
    model_config = ConfigDict(from_attributes=True)
