from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.pays import PaysResponse


# --- Auth ---

class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminSetupRequest(BaseModel):
    email: str
    password: str
    nom: str
    setup_key: str  # secret key to prevent abuse


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Platform stats ---

class DeviceBreakdown(BaseModel):
    mobile: int
    tablet: int
    desktop: int


class PlatformBreakdown(BaseModel):
    ios: int
    android: int
    windows: int
    macos: int
    linux: int
    other: int


class PlatformStats(BaseModel):
    total_livreurs: int
    active_livreurs: int
    total_tournees: int
    total_clients: int
    total_encaissements_fcfa: float
    sessions_total: int
    sessions_30d: int
    device_breakdown: DeviceBreakdown
    platform_breakdown: PlatformBreakdown


# --- Livreur performance ---

class LivreurPerformance(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: int
    nom: str
    email: str
    telephone: Optional[str]
    is_active: bool
    created_at: datetime
    nb_clients: int
    nb_tournees_total: int
    nb_tournees_30d: int
    nb_pains_total: int
    revenue_total: float
    revenue_30d: float
    last_activity: Optional[datetime]
    last_device: Optional[str]
    last_platform: Optional[str]
    nb_acolytes: int
    pays: Optional[PaysResponse] = None


class LivreurDetailStats(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    livreur: LivreurPerformance
    monthly_revenue: list[dict]  # [{"month": "2026-01", "revenue": 12500}]
    device_breakdown: DeviceBreakdown
    platform_breakdown: PlatformBreakdown
    recent_sessions: list[dict]  # last 10 login sessions


# --- Livreur management ---

class LivreurToggleRequest(BaseModel):
    is_active: bool


# --- Traffic ---

class TrafficEntry(BaseModel):
    id: int
    logged_in_at: datetime
    livreur_id: int
    livreur_nom: str
    user_type: str            # 'livreur' | 'acolyte'
    acolyte_nom: Optional[str]
    ip_address: Optional[str]
    device_type: str
    platform: str
    browser: str


class TrafficStats(BaseModel):
    total_sessions: int
    sessions_7d: int
    unique_ips_7d: int
    sessions_per_day: list[dict]  # [{"date": "2026-03-25", "count": 5}]
