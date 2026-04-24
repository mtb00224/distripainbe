from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.dette import DetteStatut # On importe l'Enum du modèle

class ReglementCreate(BaseModel):
    montant: Decimal
    notes: Optional[str] = None
    date_reglement: Optional[datetime] = None
    # On peut ajouter ici l'ID de celui qui encaisse si nécessaire

class ReglementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    dette_id: int
    livreur_id: Optional[int] = None
    boulangerie_id: Optional[int] = None
    montant: Decimal
    date_reglement: datetime
    notes: Optional[str] = None
    created_by_id: int
    created_at: datetime

class DetteCreate(BaseModel):
    client_id: int
    montant_initial: Decimal
    # Si la dette vient d'un livreur ou d'une boulangerie
    livreur_id: Optional[int] = None
    boulangerie_id: Optional[int] = None
    encaissement_id: Optional[int] = None
    notes: Optional[str] = None

class DetteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True) # Indispensable pour SQLAlchemy
    
    id: int
    livreur_id: Optional[int] = None
    boulangerie_id: Optional[int] = None
    client_id: int
    client_nom: Optional[str] = None # On pourra le remplir via un "property" ou une jointure
    encaissement_id: Optional[int] = None
    
    montant_initial: Decimal
    montant_restant: Decimal
    statut: DetteStatut # Utilise l'Enum pour la validation
    notes: Optional[str] = None
    created_at: datetime
    reglements: List[ReglementResponse] = []

    # Champ calculé pour le front-end
    @property
    def total_paye(self) -> Decimal:
        return sum(r.montant for r in self.reglements)