from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PortionPainCreate(BaseModel):
    nom: str
    prix_fcfa: int


class PortionPainUpdate(BaseModel):
    nom: Optional[str] = None
    prix_fcfa: Optional[int] = None
    is_active: Optional[bool] = None


class PortionPainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_id: int
    nom: str
    prix_fcfa: int
    is_active: bool
    created_at: datetime
