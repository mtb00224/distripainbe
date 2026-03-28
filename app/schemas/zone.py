from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ZoneBase(BaseModel):
    nom: str
    description: Optional[str] = None


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    nom: Optional[str] = None
    description: Optional[str] = None


class ZoneResponse(ZoneBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_id: int
    created_at: datetime
