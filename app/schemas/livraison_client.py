from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.client import ClientResponse


class LivraisonClientCreate(BaseModel):
    client_id: int
    nb_pains_livres: int
    nb_pains_retournes: int = 0


class LivraisonClientUpdate(BaseModel):
    nb_pains_livres: Optional[int] = None
    nb_pains_retournes: Optional[int] = None


class LivraisonClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tournee_id: int
    client_id: int
    livreur_id: int
    nb_pains_livres: int
    nb_pains_retournes: int
    prix_unitaire: float
    montant_du: float
    is_paid: bool
    is_termine: bool = False
    created_at: datetime
    client: Optional[ClientResponse] = None


class BulkLivraisonsCreate(BaseModel):
    livraisons: list[LivraisonClientCreate]
