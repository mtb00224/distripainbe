from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.boulangerie import StaffRole


# --- Boulangeries ---

class BoulangerieCreate(BaseModel):
    nom: str
    contact: Optional[str] = None
    address: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None


class BoulangerieUpdate(BaseModel):
    nom: Optional[str] = None
    contact: Optional[str] = None
    address: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None
    is_active: Optional[bool] = None


class BoulangerieResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    contact: Optional[str] = None
    address: Optional[str] = None
    prix_vente_pain: Optional[Decimal] = None
    is_active: bool
    created_at: datetime


# --- Staff ---

class StaffCreate(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    role_interne: StaffRole


class StaffUpdate(BaseModel):
    role_interne: Optional[StaffRole] = None
    is_active: Optional[bool] = None


class StaffPermissionsUpdate(BaseModel):
    """Permissions de navigation/action accordées à ce membre du staff."""
    permissions: List[str] = []


class StaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    username: str
    email: Optional[str] = None
    role_interne: StaffRole
    boulangerie_id: int
    is_active: bool


# --- Livreurs liés ---

class LivreurLinkRequest(BaseModel):
    """Lie un livreur existant à la boulangerie active par son username ou email."""
    identifier: str  # username ou email du livreur
    prix_achat_pain: Optional[Decimal] = None
    contact_local: Optional[str] = None


class LivreurLinkResponse(BaseModel):
    livreur_id: int
    first_name: str
    last_name: str
    username: str
    email: Optional[str] = None
    prix_achat_pain: Optional[Decimal] = None
    contact_local: Optional[str] = None
    is_active: bool


class LivreurContratUpdate(BaseModel):
    prix_achat_pain: Optional[Decimal] = None
    contact_local: Optional[str] = None
    is_active: Optional[bool] = None


# --- Dépenses ---

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
    montant_total: Decimal
    date_enregistrement: datetime


class CategorieDepenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    description: Optional[str] = None


# --- Profil AdminBoulangerie ---

class AdminBoulangerieProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: Optional[str] = None
    boulangeries: List[BoulangerieResponse] = []
