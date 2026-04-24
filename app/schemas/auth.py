from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class RegisterRequest(BaseModel):
    role: Literal["livreur", "admin_boulangerie"]
    first_name: str
    last_name: str
    username: str
    email: EmailStr
    password: str
    phone_number: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    must_change_password: bool = False
    # Champs spécifiques à admin_boulangerie (None pour les autres rôles)
    admin_boulangerie_id: Optional[int] = None
    boulangerie_active_id: Optional[int] = None


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Optional[str] = None
    admin_boulangerie_id: Optional[int] = None
    boulangerie_active_id: Optional[int] = None


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    username: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    role: str
    is_active: bool
    permissions: Optional[list[str]] = None
    livreur_id: Optional[int] = None
    livreur_principal_id: Optional[int] = None


class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangePasswordLivreurRequest(BaseModel):
    current_password: str
    new_password: str
