from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.zone import ZoneResponse
from app.schemas.pays import PaysResponse


class ClientBase(BaseModel):
    nom: str
    zone_id: Optional[int] = None
    pays_id: Optional[int] = None
    telephone: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    nom: Optional[str] = None
    zone_id: Optional[int] = None
    pays_id: Optional[int] = None
    telephone: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_id: int
    solde_actuel: float
    prix_vente_pain: Optional[float] = None
    is_active: bool
    created_at: datetime
    zone: Optional[ZoneResponse] = None
    pays: Optional[PaysResponse] = None


class ClientSoldeResponse(BaseModel):
    client_id: int
    nom: str
    solde_actuel: float
    statut: str
