from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

# =====================
# Base Schema
# =====================
class BoulangerieBase(BaseModel):
    nom: str
    contact: Optional[str] = None
    address: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None

# =====================
# Create / Update
# =====================
class BoulangerieCreate(BoulangerieBase):
    # On peut ajouter ici des champs requis uniquement à la création
    pass

class BoulangerieUpdate(BaseModel):
    nom: Optional[str] = None
    contact: Optional[str] = None
    address: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None
    is_active: Optional[bool] = None

# =====================
# Response Schemas
# =====================
class BoulangerieResponse(BoulangerieBase):
    model_config = ConfigDict(from_attributes=True) # Permet de lire les objets SQLAlchemy

    id: int
    is_active: bool
    created_at: datetime
    # On ne met pas forcément l'owner_id ici pour ne pas exposer trop d'infos
    # mais on pourrait ajouter le nom du patron plus tard.

# =====================
# Dépenses (Pour l'intégration)
# =====================
class CategorieDepenseBase(BaseModel):
    nom: str
    description: Optional[str] = None

class DepenseCreate(BaseModel):
    categorie_id: int
    motif: str
    quantite: Decimal = Decimal("1.0")
    prix_unitaire: Decimal

class DepenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    motif: str
    quantite: Decimal
    prix_unitaire: Decimal
    montant_total: Decimal # Ce champ sera calculé par la @property du modèle
    date_enregistrement: datetime
    categorie: CategorieDepenseBase # On peut inclure les infos de la catégorie pour plus de clarté