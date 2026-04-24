from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict


# --- Auth Admin ---

class AdminSetupRequest(BaseModel):
    setup_key: str
    email: str
    username: str
    password: str
    first_name: str
    last_name: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Statistiques Globales ---

class DeviceBreakdown(BaseModel):
    mobile: int = 0
    tablet: int = 0
    desktop: int = 0


class PlatformBreakdown(BaseModel):
    ios: int = 0
    android: int = 0
    windows: int = 0
    macos: int = 0
    linux: int = 0
    other: int = 0


class PlatformStats(BaseModel):
    total_livreurs: int
    active_livreurs: int
    total_boulangeries: int
    total_tournees: int
    total_clients: int
    sessions_total: int
    sessions_30d: int
    device_breakdown: DeviceBreakdown
    platform_breakdown: PlatformBreakdown


# --- Performance Livreur ---

class LivreurPerformance(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    created_at: datetime
    nb_clients: int
    nb_tournees_total: int
    nb_tournees_30d: int
    nb_pains_total: int
    revenue_total: float
    revenue_30d: float
    last_activity: Optional[datetime] = None
    last_device: Optional[str] = None
    last_platform: Optional[str] = None
    nb_acolytes: int


class LivreurDetailStats(BaseModel):
    livreur: LivreurPerformance
    monthly_revenue: List[Dict]
    device_breakdown: DeviceBreakdown
    platform_breakdown: PlatformBreakdown
    recent_sessions: List[Dict]


class LivreurToggleRequest(BaseModel):
    is_active: bool


class LivreurPermissionsUpdate(BaseModel):
    permissions: Optional[list[str]] = None


# --- Traffic & Sessions ---

class TrafficEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    logged_in_at: datetime
    user_id: int
    username: str
    role: str
    ip_address: Optional[str] = None
    device_type: str
    platform: str
    browser: Optional[str] = None


class TrafficStats(BaseModel):
    total_sessions: int
    sessions_7d: int
    unique_ips_7d: int
    sessions_per_day: List[Dict]
