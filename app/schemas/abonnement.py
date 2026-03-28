from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.pays import PaysResponse


class FormulaAbonnementCreate(BaseModel):
    pays_id: Optional[int] = None
    nom: str
    duree_mois: int
    prix: Decimal
    description: Optional[str] = None


class FormulaAbonnementUpdate(BaseModel):
    pays_id: Optional[int] = None
    nom: Optional[str] = None
    duree_mois: Optional[int] = None
    prix: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class FormulaAbonnementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pays_id: Optional[int] = None
    pays: Optional[PaysResponse] = None
    nom: str
    duree_mois: int
    prix: float
    description: Optional[str] = None
    is_active: bool
    created_at: datetime


class AbonnementCreate(BaseModel):
    formule_id: int
    date_debut: date


class PaiementAbonnementCreate(BaseModel):
    montant: Decimal
    moyen: str
    reference: Optional[str] = None


class PaiementAbonnementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)
    id: int
    abonnement_id: int
    livreur_id: int
    livreur_nom: str
    montant: float
    moyen: str
    reference: Optional[str] = None
    statut: str
    notes_admin: Optional[str] = None
    date_paiement: datetime
    date_validation: Optional[datetime] = None
    created_at: datetime


class AbonnementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)
    id: int
    livreur_id: int
    livreur_nom: str
    formule_id: int
    formule: FormulaAbonnementResponse
    date_debut: date
    date_fin: date
    statut: str
    created_at: datetime
    paiements: list[PaiementAbonnementResponse] = []


class ValiderPaiementRequest(BaseModel):
    statut: str  # valide | rejete
    notes_admin: Optional[str] = None


class LivreurPermissionsUpdate(BaseModel):
    permissions: Optional[list[str]] = None  # None = all permissions (reset to default)
