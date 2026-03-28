from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional


class UpdateProfileRequest(BaseModel):
    nom: Optional[str] = None
    telephone: Optional[str] = None


class ChangePasswordLivreurRequest(BaseModel):
    current_password: str
    new_password: str


class RegisterRequest(BaseModel):
    nom: str
    email: EmailStr
    password: str
    telephone: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    must_change_password: bool = False


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PaysInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    code: str
    devise_nom: str
    devise_code: str


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    email: str
    telephone: Optional[str] = None
    user_type: str
    permissions: Optional[list[str]] = None
    livreur_principal_id: Optional[int] = None
    is_active: bool
    pays: Optional[PaysInfo] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 5 or len(v) > 10:
            raise ValueError("Le mot de passe doit contenir entre 5 et 10 caractères")
        if not v.isalnum():
            raise ValueError("Le mot de passe doit contenir uniquement des chiffres et/ou des lettres")
        return v
