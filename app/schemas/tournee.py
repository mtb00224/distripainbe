from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.boulangerie import BoulangerieResponse


class TourneeBase(BaseModel):
    boulangerie_id: int
    date: date
    periode: str  # 'matin' or 'soir'
    nb_pains_pris: int
    notes: Optional[str] = None


class TourneeCreate(TourneeBase):
    nb_pains_ecoules: int = 0


class TourneeUpdate(BaseModel):
    boulangerie_id: Optional[int] = None
    nb_pains_pris: Optional[int] = None
    nb_pains_ecoules: Optional[int] = None
    notes: Optional[str] = None
    statut: Optional[str] = None


class TourneeResponse(TourneeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_id: int
    nb_pains_ecoules: int
    nb_pains_retournes: int
    statut: str
    created_at: datetime
    boulangerie: Optional[BoulangerieResponse] = None
