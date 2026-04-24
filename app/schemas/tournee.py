from datetime import date as DateType, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, computed_field
from app.models.tournee import PeriodeTournee, StatutTournee, TypeTournee
from app.schemas.boulangerie import BoulangerieResponse

# =====================
# Retours détaillés
# =====================
class RetourLigneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    portion_pain_id: int
    portion_nom: str = "" # On pourra le remplir via la relation portion.nom
    quantite: int
    valeur_unitaire: float = 0.0 # Pour le calcul des équivalences

# =====================
# Tournée principale
# =====================
class TourneeBase(BaseModel):
    boulangerie_id: int
    date: DateType = Field(default_factory=DateType.today)
    periode: PeriodeTournee
    type_tournee: TypeTournee = TypeTournee.LIVREUR_PROPRE
    nb_pains_pris: int = 0
    notes: Optional[str] = None

class TourneeCreate(TourneeBase):
    # Un livreur peut préciser son ID s'il crée sa propre tournée
    livreur_id: Optional[int] = None

class TourneeUpdate(BaseModel):
    nb_pains_pris: Optional[int] = None
    nb_pains_ecoules: Optional[int] = None
    nb_pains_retournes: Optional[int] = None
    statut: Optional[StatutTournee] = None
    notes: Optional[str] = None

class TourneeResponse(TourneeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_id: Optional[int] = None
    nb_pains_ecoules: int
    nb_pains_retournes: int
    statut: StatutTournee
    created_at: datetime
    created_by_id: int
    
    # Inclusion des relations pour un affichage complet
    boulangerie: Optional[BoulangerieResponse] = None
    retour_lignes: List[RetourLigneResponse] = []
    
    # Champ calculé pour le front-end

    @computed_field
    @property
    def ecart(self) -> int:
        return self.nb_pains_pris - self.nb_pains_ecoules - self.nb_pains_retournes