import json
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

AVAILABLE_PERMISSIONS = [
    "read_clients", "write_clients",
    "read_boulangeries", "write_boulangeries",
    "read_zones", "write_zones",
    "read_tournees", "create_tournees", "update_tournees", "terminer_tournees",
    "write_livraisons",
    "read_encaissements", "write_encaissements",
    "read_stats",
]


class AcolyteCreate(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    permissions: List[str] = []

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        for p in v:
            if p not in AVAILABLE_PERMISSIONS:
                raise ValueError(f"Permission invalide : {p}")
        return v


class AcolyteUpdate(BaseModel):
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AcolyteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    livreur_principal_id: int
    permissions: List[str] = []
    is_active: bool
    is_default_password: bool = False
    created_at: datetime
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    email: Optional[str] = None

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if hasattr(obj, "permissions") and isinstance(obj.permissions, str):
            try:
                obj.permissions = json.loads(obj.permissions)
            except (ValueError, TypeError):
                obj.permissions = []
        res = super().model_validate(obj, *args, **kwargs)
        if hasattr(obj, "user") and obj.user:
            res.first_name = obj.user.first_name
            res.last_name = obj.user.last_name
            res.username = obj.user.username
            res.email = obj.user.email
            res.is_default_password = obj.user.must_change_password
        return res
