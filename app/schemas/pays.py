from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PaysCreate(BaseModel):
    nom: str
    code: str
    devise_nom: str
    devise_code: str


class PaysUpdate(BaseModel):
    nom: Optional[str] = None
    devise_nom: Optional[str] = None
    devise_code: Optional[str] = None
    is_active: Optional[bool] = None


class PaysResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    code: str
    devise_nom: str
    devise_code: str
    is_active: bool
    created_at: datetime
