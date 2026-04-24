from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LivreurInterneCreate(BaseModel):
    prenom: str
    nom: str
    telephone: Optional[str] = None
    prix_achat_pain: Optional[Decimal] = None
    boulangerie_ids: list[int]  # Au moins une boulangerie requise


class LivreurInterneUpdate(BaseModel):
    prenom: Optional[str] = None
    nom: Optional[str] = None
    telephone: Optional[str] = None
    prix_achat_pain: Optional[Decimal] = None
    is_active: Optional[bool] = None


class LivreurInterneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    boulangerie_id: int
    prenom: str
    nom: str
    telephone: Optional[str] = None
    prix_achat_pain: Optional[Decimal] = None
    user_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    # Solde du compte interne (None si pas de compte ouvert)
    solde_compte: Optional[Decimal] = None


class CompteInterneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_interne_id: int
    solde_actuel: Decimal
    updated_at: datetime


class RetraitCreate(BaseModel):
    montant: Decimal
    notes: Optional[str] = None


class RetraitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    compte_id: int
    montant: Decimal
    date_retrait: datetime
    notes: Optional[str] = None
