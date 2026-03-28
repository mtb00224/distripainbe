from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class BoulangerieBase(BaseModel):
    nom: str
    contact: Optional[str] = None
    prix_achat_pain: Optional[Decimal] = None


class BoulangerieCreate(BoulangerieBase):
    pass


class BoulangerieUpdate(BaseModel):
    nom: Optional[str] = None
    contact: Optional[str] = None
    prix_achat_pain: Optional[Decimal] = None
    is_active: Optional[bool] = None


class BoulangerieResponse(BoulangerieBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_id: int
    prix_achat_pain: Optional[float] = None
    is_default: bool
    is_active: bool
    created_at: datetime
