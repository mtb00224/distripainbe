from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ReglementCreate(BaseModel):
    montant: Decimal
    notes: Optional[str] = None
    date_reglement: Optional[datetime] = None


class ReglementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dette_id: int
    livreur_id: int
    montant: float
    date_reglement: datetime
    notes: Optional[str] = None
    created_at: datetime


class DetteCreate(BaseModel):
    client_id: int
    montant_initial: Decimal
    livraison_ids: list[int] = []
    notes: Optional[str] = None


class DetteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)
    id: int
    livreur_id: int
    client_id: int
    client_nom: str
    zone_nom: Optional[str] = None
    encaissement_id: Optional[int]
    livraison_ids: list[int]
    montant_initial: float
    montant_restant: float
    statut: str
    notes: Optional[str]
    created_at: datetime
    reglements: list[ReglementResponse] = []
