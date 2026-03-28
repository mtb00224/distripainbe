from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.pays import PaysResponse


class MoyenPaiementCreate(BaseModel):
    pays_id: Optional[int] = None
    nom: str
    numero: str
    instructions: Optional[str] = None


class MoyenPaiementUpdate(BaseModel):
    nom: Optional[str] = None
    numero: Optional[str] = None
    instructions: Optional[str] = None
    is_active: Optional[bool] = None
    pays_id: Optional[int] = None


class MoyenPaiementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pays_id: Optional[int] = None
    pays: Optional[PaysResponse] = None
    nom: str
    numero: str
    instructions: Optional[str] = None
    is_active: bool
    created_at: datetime
