from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

# Importation du schéma de zone pour la réponse détaillée
from app.schemas.zone import ZoneResponse

class ClientBase(BaseModel):
    nom: str
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None
    zone_id: Optional[int] = None

class ClientCreate(ClientBase):
    # Facultatif selon qui crée (Livreur ou Boulangerie)
    livreur_id: Optional[int] = None
    boulangerie_id: Optional[int] = None

class ClientUpdate(BaseModel):
    nom: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None
    zone_id: Optional[int] = None
    is_active: Optional[bool] = None

class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_id: Optional[int] = None
    boulangerie_id: Optional[int] = None
    created_by_id: int
    solde_actuel: Decimal # Gardé en Decimal pour la précision
    is_active: bool
    created_at: datetime
    
    # Détails de la zone si elle existe
    zone: Optional[ZoneResponse] = None

class ClientSoldeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    client_id: int
    nom: str
    solde_actuel: Decimal
    # Le statut peut être "créditeur" ou "débiteur" par exemple
    statut: str 