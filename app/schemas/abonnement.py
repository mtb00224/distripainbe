from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.abonnement import AbonnementStatut, PaiementStatut, CibleAbonnement

# --- FORMULES ---

class FormulaAbonnementBase(BaseModel):
    nom: str
    cible: CibleAbonnement
    duree_mois: int
    prix: Decimal
    max_boulangeries: Optional[int] = None # Null pour les livreurs, Entier pour les patrons
    description: Optional[str] = None

class FormulaAbonnementCreate(FormulaAbonnementBase):
    pass

class FormulaAbonnementUpdate(BaseModel):
    nom: Optional[str] = None
    cible: Optional[CibleAbonnement] = None
    duree_mois: Optional[int] = None
    prix: Optional[Decimal] = None
    max_boulangeries: Optional[int] = None
    is_active: Optional[bool] = None

class FormulaAbonnementResponse(FormulaAbonnementBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime

# --- PAIEMENTS ---

class PaiementAbonnementCreate(BaseModel):
    abonnement_id: int
    montant: Decimal
    reference: Optional[str] = None # ID de transaction Wave/OM/etc.

class PaiementAbonnementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    abonnement_id: int
    montant: Decimal
    reference: Optional[str] = None
    statut: PaiementStatut
    date_paiement: datetime
    valide_par_id: Optional[int] = None # Admin qui a validé
    date_validation: Optional[datetime] = None

# --- ABONNEMENTS ---

class AbonnementCreate(BaseModel):
    formule_id: int
    # Flexible : l'un des deux doit être fourni selon le profil
    livreur_id: Optional[int] = None
    boulangerie_id: Optional[int] = None
    date_debut: Optional[date] = None # Par défaut aujourd'hui si None

class AbonnementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    livreur_id: Optional[int] = None
    boulangerie_id: Optional[int] = None
    formule_id: int
    formule: FormulaAbonnementResponse
    date_debut: date
    date_fin: date
    statut: AbonnementStatut
    created_at: datetime
    paiements: List[PaiementAbonnementResponse] = []

# --- ACTIONS ADMIN ---

class ValiderPaiementRequest(BaseModel):
    statut: PaiementStatut # valide | rejete
    notes_admin: Optional[str] = None
