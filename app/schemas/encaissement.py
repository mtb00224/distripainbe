from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.client import ClientResponse


class EncaissementCreate(BaseModel):
    client_id: int
    montant: Decimal
    livraisons_soldees: list[int]
    type: str  # 'complet', 'partiel', 'avance'
    notes: Optional[str] = None
    date_encaissement: Optional[datetime] = None


class EncaissementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_id: int
    client_id: int
    montant: float
    date_encaissement: datetime
    livraisons_soldees: list[int]
    type: str
    notes: Optional[str] = None
    created_at: datetime
    client: Optional[ClientResponse] = None

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        import json
        if hasattr(obj, 'livraisons_soldees') and isinstance(obj.livraisons_soldees, str):
            try:
                obj.livraisons_soldees = json.loads(obj.livraisons_soldees)
            except (ValueError, TypeError):
                obj.livraisons_soldees = []
        return super().model_validate(obj, *args, **kwargs)


class PendingLivraisonResponse(BaseModel):
    client_id: int
    client_nom: str
    livraison_id: int
    tournee_id: int
    tournee_date: str
    tournee_periode: str
    montant_du: float
    nb_pains_livres: int
    nb_pains_retournes: int


class PendingTourneeResponse(BaseModel):
    """Pending livraisons grouped by tournée with existing debt info."""
    tournee_id: int
    tournee_date: str
    tournee_periode: str
    livraison_ids: list[int]
    total_montant_du: float      # original total for this tournée
    montant_deja_paye: float     # already paid via prior partial payments
    montant_restant: float       # still owed (= dette.montant_restant if active dette, else total)
    dette_id: Optional[int]      # active dette linked to this tournée, if any
    nb_pains_nets: int           # pains livrés - retournés


class ClientWithPendingResponse(BaseModel):
    client_id: int
    client_nom: str
    zone_nom: Optional[str] = None
    telephone: Optional[str] = None
    solde_actuel: float
    nb_tournees_pending: int
    montant_total_pending: float
