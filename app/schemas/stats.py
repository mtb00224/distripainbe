from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class StatsPeriodeResponse(BaseModel):
    periode: str
    total_pains_pris: int
    total_pains_ecoules: int
    total_pains_retournes: int
    total_montant_du: float
    total_encaisse: float
    taux_ecoulement: float
    boulangerie_id: Optional[int] = None
    nb_tournees: int


class StatsClientResponse(BaseModel):
    client_id: int
    client_nom: str
    total_livraisons: int
    total_pains_livres: int
    montant_total_du: float
    montant_encaisse: float
    solde: float
    statut: str
