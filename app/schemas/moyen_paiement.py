from typing import Optional
from pydantic import BaseModel, ConfigDict


class MoyenPaiementCreate(BaseModel):
    nom: str
    numero: str
    instructions: Optional[str] = None


class MoyenPaiementUpdate(BaseModel):
    nom: Optional[str] = None
    numero: Optional[str] = None
    instructions: Optional[str] = None
    is_active: Optional[bool] = None


class MoyenPaiementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    numero: str
    instructions: Optional[str] = None
    is_active: bool
