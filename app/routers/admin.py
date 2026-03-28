"""Global platform administration router.

Auth:
  POST /admin/auth/setup, POST /admin/auth/login

Stats:
  GET /admin/stats

Livreurs:
  GET/PATCH /admin/livreurs, GET /admin/livreurs/{id}
  GET/PUT   /admin/livreurs/{id}/permissions

Traffic:
  GET /admin/traffic, GET /admin/traffic/stats, DELETE /admin/traffic/{id}

Pays:
  GET/POST /admin/pays, PUT/DELETE /admin/pays/{id}

Formules abonnement:
  GET/POST /admin/formules-abonnement, PUT/DELETE /admin/formules-abonnement/{id}

Abonnements:
  GET /admin/abonnements
  POST /admin/abonnements/{id}/paiements/{pid}/valider

Moyens de paiement:
  GET/POST /admin/moyens-paiement, PUT/DELETE /admin/moyens-paiement/{id}
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.session import get_db
import json
from app.models.abonnement import Abonnement, FormulaAbonnement, PaiementAbonnement
from app.models.admin import Admin
from app.models.acolyte import Acolyte
from app.models.client import Client
from app.models.encaissement import Encaissement
from app.models.livreur import Livreur
from app.models.moyen_paiement import MoyenPaiement
from app.models.pays import Pays
from app.models.tournee import Tournee
from app.models.user_session import UserSession
from sqlalchemy.orm import aliased, selectinload
from app.schemas.abonnement import (
    AbonnementResponse,
    FormulaAbonnementCreate,
    FormulaAbonnementResponse,
    FormulaAbonnementUpdate,
    LivreurPermissionsUpdate,
    PaiementAbonnementResponse,
    ValiderPaiementRequest,
)
from app.schemas.moyen_paiement import (
    MoyenPaiementCreate,
    MoyenPaiementResponse,
    MoyenPaiementUpdate,
)
from app.schemas.pays import PaysCreate, PaysResponse, PaysUpdate
from app.schemas.admin import (
    AdminLoginRequest,
    AdminSetupRequest,
    AdminTokenResponse,
    DeviceBreakdown,
    LivreurDetailStats,
    LivreurPerformance,
    LivreurToggleRequest,
    PlatformBreakdown,
    PlatformStats,
    TrafficEntry,
    TrafficStats,
)

router = APIRouter(prefix="/admin", tags=["admin"])
bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Admin JWT helpers
# ---------------------------------------------------------------------------

def _create_admin_token(admin_id: int) -> str:
    return create_access_token({"sub": str(admin_id), "user_type": "admin"})


async def _get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("user_type") != "admin":
            raise HTTPException(status_code=403, detail="Accès réservé aux admins")
        admin_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    result = await db.execute(select(Admin).where(Admin.id == admin_id, Admin.is_active == True))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin introuvable")
    return admin


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/setup", response_model=AdminTokenResponse, status_code=status.HTTP_201_CREATED)
async def setup_admin(payload: AdminSetupRequest, db: AsyncSession = Depends(get_db)):
    """Create the platform admin account. Can only be called when no admin exists yet."""
    if payload.setup_key != settings.ADMIN_SETUP_KEY:
        raise HTTPException(status_code=403, detail="Clé de configuration invalide")

    existing = await db.execute(select(Admin).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Un compte admin existe déjà")

    admin = Admin(
        email=payload.email,
        password_hash=hash_password(payload.password),
        nom=payload.nom,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return AdminTokenResponse(access_token=_create_admin_token(admin.id))


@router.post("/auth/login", response_model=AdminTokenResponse)
async def login_admin(payload: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.email == payload.email))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    return AdminTokenResponse(access_token=_create_admin_token(admin.id))


# ---------------------------------------------------------------------------
# Platform stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=PlatformStats)
async def get_platform_stats(
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    since_30d = datetime.now(timezone.utc) - timedelta(days=30)

    # Livreur counts
    r = await db.execute(select(func.count()).select_from(Livreur))
    total_livreurs = r.scalar_one()
    r = await db.execute(select(func.count()).select_from(Livreur).where(Livreur.is_active == True))
    active_livreurs = r.scalar_one()

    # Tournées
    r = await db.execute(select(func.count()).select_from(Tournee))
    total_tournees = r.scalar_one()

    # Clients
    r = await db.execute(select(func.count()).select_from(Client).where(Client.is_active == True))
    total_clients = r.scalar_one()

    # Encaissements (exclude dettes)
    r = await db.execute(
        select(func.coalesce(func.sum(Encaissement.montant), 0))
        .where(Encaissement.type != "dette")
    )
    total_enc = float(r.scalar_one())

    # Sessions
    r = await db.execute(select(func.count()).select_from(UserSession))
    sessions_total = r.scalar_one()
    r = await db.execute(
        select(func.count()).select_from(UserSession)
        .where(UserSession.logged_in_at >= since_30d)
    )
    sessions_30d = r.scalar_one()

    # Device breakdown (all time)
    r = await db.execute(
        select(UserSession.device_type, func.count().label("cnt"))
        .group_by(UserSession.device_type)
    )
    device_counts = {row.device_type: row.cnt for row in r.all()}

    # Platform breakdown
    r = await db.execute(
        select(UserSession.platform, func.count().label("cnt"))
        .group_by(UserSession.platform)
    )
    platform_counts = {row.platform: row.cnt for row in r.all()}

    return PlatformStats(
        total_livreurs=total_livreurs,
        active_livreurs=active_livreurs,
        total_tournees=total_tournees,
        total_clients=total_clients,
        total_encaissements_fcfa=total_enc,
        sessions_total=sessions_total,
        sessions_30d=sessions_30d,
        device_breakdown=DeviceBreakdown(
            mobile=device_counts.get("mobile", 0),
            tablet=device_counts.get("tablet", 0),
            desktop=device_counts.get("desktop", 0),
        ),
        platform_breakdown=PlatformBreakdown(
            ios=platform_counts.get("iOS", 0),
            android=platform_counts.get("Android", 0),
            windows=platform_counts.get("Windows", 0),
            macos=platform_counts.get("macOS", 0),
            linux=platform_counts.get("Linux", 0),
            other=sum(v for k, v in platform_counts.items() if k not in ("iOS", "Android", "Windows", "macOS", "Linux")),
        ),
    )


# ---------------------------------------------------------------------------
# Livreurs management
# ---------------------------------------------------------------------------

async def _build_livreur_perf(db: AsyncSession, livreur: Livreur) -> LivreurPerformance:
    since_30d = datetime.now(timezone.utc) - timedelta(days=30)

    # nb_clients
    r = await db.execute(
        select(func.count()).select_from(Client)
        .where(Client.livreur_id == livreur.id, Client.is_active == True)
    )
    nb_clients = r.scalar_one()

    # nb_tournees total + 30d
    r = await db.execute(
        select(func.count()).select_from(Tournee).where(Tournee.livreur_id == livreur.id)
    )
    nb_tournees_total = r.scalar_one()
    r = await db.execute(
        select(func.count()).select_from(Tournee)
        .where(Tournee.livreur_id == livreur.id, Tournee.created_at >= since_30d)
    )
    nb_tournees_30d = r.scalar_one()

    # nb_pains total (sum of nb_pains_ecoules across all tournées)
    r = await db.execute(
        select(func.coalesce(func.sum(Tournee.nb_pains_ecoules), 0))
        .where(Tournee.livreur_id == livreur.id)
    )
    nb_pains_total = int(r.scalar_one())

    # revenue total + 30d (encaissements, exclude dettes)
    r = await db.execute(
        select(func.coalesce(func.sum(Encaissement.montant), 0))
        .where(Encaissement.livreur_id == livreur.id, Encaissement.type != "dette")
    )
    revenue_total = float(r.scalar_one())

    r = await db.execute(
        select(func.coalesce(func.sum(Encaissement.montant), 0))
        .where(
            Encaissement.livreur_id == livreur.id,
            Encaissement.type != "dette",
            Encaissement.date_encaissement >= since_30d,
        )
    )
    revenue_30d = float(r.scalar_one())

    # Last activity (most recent tournée)
    r = await db.execute(
        select(func.max(Tournee.created_at)).where(Tournee.livreur_id == livreur.id)
    )
    last_activity = r.scalar_one()

    # Last session device info
    r = await db.execute(
        select(UserSession)
        .where(UserSession.livreur_id == livreur.id)
        .order_by(UserSession.logged_in_at.desc())
        .limit(1)
    )
    last_session = r.scalar_one_or_none()

    # nb_acolytes
    r = await db.execute(
        select(func.count()).select_from(Acolyte)
        .where(Acolyte.livreur_principal_id == livreur.id, Acolyte.is_active == True)
    )
    nb_acolytes = r.scalar_one()

    pays_info = PaysResponse.model_validate(livreur.pays) if livreur.pays else None

    return LivreurPerformance(
        id=livreur.id,
        nom=livreur.nom,
        email=livreur.email,
        telephone=livreur.telephone,
        is_active=livreur.is_active,
        created_at=livreur.created_at,
        nb_clients=nb_clients,
        nb_tournees_total=nb_tournees_total,
        nb_tournees_30d=nb_tournees_30d,
        nb_pains_total=nb_pains_total,
        revenue_total=revenue_total,
        revenue_30d=revenue_30d,
        last_activity=last_activity,
        last_device=last_session.device_type if last_session else None,
        last_platform=last_session.platform if last_session else None,
        nb_acolytes=nb_acolytes,
        pays=pays_info,
    )


@router.get("/livreurs", response_model=list[LivreurPerformance])
async def list_livreurs(
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Livreur).options(selectinload(Livreur.pays)).order_by(Livreur.created_at.desc())
    )
    livreurs = result.scalars().all()
    return [await _build_livreur_perf(db, lv) for lv in livreurs]


@router.get("/livreurs/{livreur_id}", response_model=LivreurDetailStats)
async def get_livreur_detail(
    livreur_id: int,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Livreur).options(selectinload(Livreur.pays)).where(Livreur.id == livreur_id)
    )
    livreur = result.scalar_one_or_none()
    if not livreur:
        raise HTTPException(status_code=404, detail="Livreur introuvable")

    perf = await _build_livreur_perf(db, livreur)

    # Monthly revenue (last 12 months)
    since_12m = datetime.now(timezone.utc) - timedelta(days=365)
    r = await db.execute(
        select(
            func.strftime("%Y-%m", Encaissement.date_encaissement).label("month"),
            func.sum(Encaissement.montant).label("revenue"),
        )
        .where(
            Encaissement.livreur_id == livreur_id,
            Encaissement.type != "dette",
            Encaissement.date_encaissement >= since_12m,
        )
        .group_by("month")
        .order_by("month")
    )
    monthly_revenue = [{"month": row.month, "revenue": float(row.revenue or 0)} for row in r.all()]

    # Device breakdown for this livreur
    r = await db.execute(
        select(UserSession.device_type, func.count().label("cnt"))
        .where(UserSession.livreur_id == livreur_id)
        .group_by(UserSession.device_type)
    )
    device_counts = {row.device_type: row.cnt for row in r.all()}

    r = await db.execute(
        select(UserSession.platform, func.count().label("cnt"))
        .where(UserSession.livreur_id == livreur_id)
        .group_by(UserSession.platform)
    )
    platform_counts = {row.platform: row.cnt for row in r.all()}

    # Recent sessions (last 10)
    r = await db.execute(
        select(UserSession)
        .where(UserSession.livreur_id == livreur_id)
        .order_by(UserSession.logged_in_at.desc())
        .limit(10)
    )
    recent_sessions = [
        {
            "logged_in_at": s.logged_in_at.isoformat(),
            "device_type": s.device_type,
            "platform": s.platform,
            "browser": s.browser,
        }
        for s in r.scalars().all()
    ]

    return LivreurDetailStats(
        livreur=perf,
        monthly_revenue=monthly_revenue,
        device_breakdown=DeviceBreakdown(
            mobile=device_counts.get("mobile", 0),
            tablet=device_counts.get("tablet", 0),
            desktop=device_counts.get("desktop", 0),
        ),
        platform_breakdown=PlatformBreakdown(
            ios=platform_counts.get("iOS", 0),
            android=platform_counts.get("Android", 0),
            windows=platform_counts.get("Windows", 0),
            macos=platform_counts.get("macOS", 0),
            linux=platform_counts.get("Linux", 0),
            other=sum(v for k, v in platform_counts.items() if k not in ("iOS", "Android", "Windows", "macOS", "Linux")),
        ),
        recent_sessions=recent_sessions,
    )


@router.patch("/livreurs/{livreur_id}", response_model=LivreurPerformance)
async def toggle_livreur(
    livreur_id: int,
    payload: LivreurToggleRequest,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Livreur).where(Livreur.id == livreur_id))
    livreur = result.scalar_one_or_none()
    if not livreur:
        raise HTTPException(status_code=404, detail="Livreur introuvable")
    livreur.is_active = payload.is_active
    db.add(livreur)
    await db.commit()
    await db.refresh(livreur)
    return await _build_livreur_perf(db, livreur)


# ---------------------------------------------------------------------------
# Traffic / sessions log
# ---------------------------------------------------------------------------

@router.get("/traffic/stats", response_model=TrafficStats)
async def get_traffic_stats(
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    since_7d = datetime.now(timezone.utc) - timedelta(days=7)

    r = await db.execute(select(func.count()).select_from(UserSession))
    total_sessions = r.scalar_one()

    r = await db.execute(
        select(func.count()).select_from(UserSession)
        .where(UserSession.logged_in_at >= since_7d)
    )
    sessions_7d = r.scalar_one()

    r = await db.execute(
        select(func.count(func.distinct(UserSession.ip_address)))
        .where(UserSession.logged_in_at >= since_7d, UserSession.ip_address.isnot(None))
    )
    unique_ips_7d = r.scalar_one()

    # Sessions per day for last 14 days
    since_14d = datetime.now(timezone.utc) - timedelta(days=14)
    r = await db.execute(
        select(
            func.strftime("%Y-%m-%d", UserSession.logged_in_at).label("day"),
            func.count().label("cnt"),
        )
        .where(UserSession.logged_in_at >= since_14d)
        .group_by("day")
        .order_by("day")
    )
    sessions_per_day = [{"date": row.day, "count": row.cnt} for row in r.all()]

    return TrafficStats(
        total_sessions=total_sessions,
        sessions_7d=sessions_7d,
        unique_ips_7d=unique_ips_7d,
        sessions_per_day=sessions_per_day,
    )


@router.delete("/traffic/{session_id}", status_code=204)
async def delete_traffic_session(
    session_id: int,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserSession).where(UserSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    await db.delete(session)
    await db.commit()


@router.get("/traffic", response_model=list[TrafficEntry])
async def get_traffic(
    limit: int = 100,
    offset: int = 0,
    livreur_id: Optional[int] = None,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    AcolyteAlias = aliased(Acolyte)
    q = (
        select(
            UserSession,
            Livreur.nom.label("livreur_nom"),
            AcolyteAlias.nom.label("acolyte_nom"),
        )
        .join(Livreur, Livreur.id == UserSession.livreur_id)
        .outerjoin(AcolyteAlias, AcolyteAlias.id == UserSession.acolyte_id)
        .order_by(UserSession.logged_in_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if livreur_id:
        q = q.where(UserSession.livreur_id == livreur_id)

    result = await db.execute(q)
    rows = result.all()

    return [
        TrafficEntry(
            id=s.id,
            logged_in_at=s.logged_in_at,
            livreur_id=s.livreur_id,
            livreur_nom=livreur_nom,
            user_type=s.user_type or "livreur",
            acolyte_nom=acolyte_nom,
            ip_address=s.ip_address,
            device_type=s.device_type,
            platform=s.platform,
            browser=s.browser,
        )
        for s, livreur_nom, acolyte_nom in rows
    ]


# ===========================================================================
# Pays
# ===========================================================================

@router.get("/pays", response_model=list[PaysResponse])
async def list_pays(
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pays).order_by(Pays.nom))
    return result.scalars().all()


@router.post("/pays", response_model=PaysResponse, status_code=status.HTTP_201_CREATED)
async def create_pays(
    payload: PaysCreate,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Pays).where(Pays.code == payload.code.upper()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ce code pays existe déjà")
    data = payload.model_dump()
    data['code'] = data['code'].upper()
    pays = Pays(**data)
    db.add(pays)
    await db.commit()
    await db.refresh(pays)
    return pays


@router.put("/pays/{pays_id}", response_model=PaysResponse)
async def update_pays(
    pays_id: int,
    payload: PaysUpdate,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    pays = await db.get(Pays, pays_id)
    if not pays:
        raise HTTPException(status_code=404, detail="Pays introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(pays, field, value)
    db.add(pays)
    await db.commit()
    await db.refresh(pays)
    return pays


@router.delete("/pays/{pays_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pays(
    pays_id: int,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    pays = await db.get(Pays, pays_id)
    if not pays:
        raise HTTPException(status_code=404, detail="Pays introuvable")
    await db.delete(pays)
    await db.commit()


# ===========================================================================
# Formules d'abonnement
# ===========================================================================

@router.get("/formules-abonnement", response_model=list[FormulaAbonnementResponse])
async def list_formules(
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FormulaAbonnement)
        .options(selectinload(FormulaAbonnement.pays))
        .order_by(FormulaAbonnement.pays_id.nullsfirst(), FormulaAbonnement.duree_mois)
    )
    return result.scalars().all()


async def _refresh_formule(db: AsyncSession, formule_id: int) -> FormulaAbonnement:
    result = await db.execute(
        select(FormulaAbonnement)
        .options(selectinload(FormulaAbonnement.pays))
        .where(FormulaAbonnement.id == formule_id)
    )
    return result.scalar_one()


@router.post("/formules-abonnement", response_model=FormulaAbonnementResponse,
             status_code=status.HTTP_201_CREATED)
async def create_formule(
    payload: FormulaAbonnementCreate,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    formule = FormulaAbonnement(**payload.model_dump())
    db.add(formule)
    await db.commit()
    return await _refresh_formule(db, formule.id)


@router.put("/formules-abonnement/{formule_id}", response_model=FormulaAbonnementResponse)
async def update_formule(
    formule_id: int,
    payload: FormulaAbonnementUpdate,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    formule = await db.get(FormulaAbonnement, formule_id)
    if not formule:
        raise HTTPException(status_code=404, detail="Formule introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(formule, field, value)
    db.add(formule)
    await db.commit()
    return await _refresh_formule(db, formule_id)
    return formule


@router.delete("/formules-abonnement/{formule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_formule(
    formule_id: int,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    formule = await db.get(FormulaAbonnement, formule_id)
    if not formule:
        raise HTTPException(status_code=404, detail="Formule introuvable")
    await db.delete(formule)
    await db.commit()


# ===========================================================================
# Abonnements (admin view — all livreurs)
# ===========================================================================

def _build_admin_paiement(p: PaiementAbonnement, livreur_nom: str) -> PaiementAbonnementResponse:
    return PaiementAbonnementResponse(
        id=p.id, abonnement_id=p.abonnement_id, livreur_id=p.livreur_id,
        livreur_nom=livreur_nom, montant=float(p.montant), moyen=p.moyen,
        reference=p.reference, statut=p.statut, notes_admin=p.notes_admin,
        date_paiement=p.date_paiement, date_validation=p.date_validation,
        created_at=p.created_at,
    )


def _build_admin_abonnement(a: Abonnement) -> AbonnementResponse:
    nom = a.livreur.nom if a.livreur else f"Livreur #{a.livreur_id}"
    from app.schemas.abonnement import FormulaAbonnementResponse as FR
    return AbonnementResponse(
        id=a.id, livreur_id=a.livreur_id, livreur_nom=nom,
        formule_id=a.formule_id,
        formule=FR(
            id=a.formule.id, nom=a.formule.nom, duree_mois=a.formule.duree_mois,
            prix=float(a.formule.prix), description=a.formule.description,
            is_active=a.formule.is_active, created_at=a.formule.created_at,
        ),
        date_debut=a.date_debut, date_fin=a.date_fin,
        statut=a.statut, created_at=a.created_at,
        paiements=[_build_admin_paiement(p, nom) for p in a.paiements],
    )


@router.get("/abonnements", response_model=list[AbonnementResponse])
async def list_abonnements(
    livreur_id: Optional[int] = None,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Abonnement)
        .options(
            selectinload(Abonnement.formule),
            selectinload(Abonnement.paiements),
            selectinload(Abonnement.livreur),
        )
        .order_by(Abonnement.created_at.desc())
    )
    if livreur_id:
        q = q.where(Abonnement.livreur_id == livreur_id)
    result = await db.execute(q)
    return [_build_admin_abonnement(a) for a in result.scalars().all()]


@router.post("/abonnements/{abonnement_id}/paiements/{paiement_id}/valider",
             response_model=AbonnementResponse)
async def valider_paiement(
    abonnement_id: int,
    paiement_id: int,
    payload: ValiderPaiementRequest,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if payload.statut not in ("valide", "rejete"):
        raise HTTPException(status_code=400, detail="statut doit être 'valide' ou 'rejete'")

    result = await db.execute(
        select(PaiementAbonnement).where(
            PaiementAbonnement.id == paiement_id,
            PaiementAbonnement.abonnement_id == abonnement_id,
        )
    )
    paiement = result.scalar_one_or_none()
    if not paiement:
        raise HTTPException(status_code=404, detail="Paiement introuvable")

    paiement.statut = payload.statut
    paiement.notes_admin = payload.notes_admin
    if payload.statut == "valide":
        paiement.date_validation = datetime.now(timezone.utc)
        # Activate the subscription
        abo = await db.get(Abonnement, abonnement_id)
        if abo:
            abo.statut = "actif"
            db.add(abo)

    db.add(paiement)
    await db.commit()

    result = await db.execute(
        select(Abonnement)
        .options(
            selectinload(Abonnement.formule),
            selectinload(Abonnement.paiements),
            selectinload(Abonnement.livreur),
        )
        .where(Abonnement.id == abonnement_id)
    )
    return _build_admin_abonnement(result.scalar_one())


# ===========================================================================
# Moyens de paiement
# ===========================================================================

@router.get("/moyens-paiement", response_model=list[MoyenPaiementResponse])
async def list_moyens_paiement(
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MoyenPaiement)
        .options(selectinload(MoyenPaiement.pays))
        .order_by(MoyenPaiement.pays_id.nullslast(), MoyenPaiement.nom)
    )
    return result.scalars().all()


@router.post("/moyens-paiement", response_model=MoyenPaiementResponse,
             status_code=status.HTTP_201_CREATED)
async def create_moyen_paiement(
    payload: MoyenPaiementCreate,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    moyen = MoyenPaiement(**payload.model_dump())
    db.add(moyen)
    await db.commit()
    result = await db.execute(
        select(MoyenPaiement).options(selectinload(MoyenPaiement.pays))
        .where(MoyenPaiement.id == moyen.id)
    )
    return result.scalar_one()


@router.put("/moyens-paiement/{moyen_id}", response_model=MoyenPaiementResponse)
async def update_moyen_paiement(
    moyen_id: int,
    payload: MoyenPaiementUpdate,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MoyenPaiement).options(selectinload(MoyenPaiement.pays))
        .where(MoyenPaiement.id == moyen_id)
    )
    moyen = result.scalar_one_or_none()
    if not moyen:
        raise HTTPException(status_code=404, detail="Moyen de paiement introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(moyen, field, value)
    db.add(moyen)
    await db.commit()
    result = await db.execute(
        select(MoyenPaiement).options(selectinload(MoyenPaiement.pays))
        .where(MoyenPaiement.id == moyen_id)
    )
    return result.scalar_one()


@router.delete("/moyens-paiement/{moyen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_moyen_paiement(
    moyen_id: int,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    moyen = await db.get(MoyenPaiement, moyen_id)
    if not moyen:
        raise HTTPException(status_code=404, detail="Moyen de paiement introuvable")
    await db.delete(moyen)
    await db.commit()


# ===========================================================================
# Livreur permissions
# ===========================================================================

@router.get("/livreurs/{livreur_id}/permissions")
async def get_livreur_permissions(
    livreur_id: int,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    livreur = await db.get(Livreur, livreur_id)
    if not livreur:
        raise HTTPException(status_code=404, detail="Livreur introuvable")
    perms = None
    if livreur.permissions is not None:
        try:
            perms = json.loads(livreur.permissions)
        except (ValueError, TypeError):
            perms = []
    return {"livreur_id": livreur_id, "permissions": perms}


@router.put("/livreurs/{livreur_id}/permissions")
async def update_livreur_permissions(
    livreur_id: int,
    payload: LivreurPermissionsUpdate,
    _admin: Admin = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    livreur = await db.get(Livreur, livreur_id)
    if not livreur:
        raise HTTPException(status_code=404, detail="Livreur introuvable")
    # None = unrestricted (full access)
    livreur.permissions = json.dumps(payload.permissions) if payload.permissions is not None else None
    db.add(livreur)
    await db.commit()
    perms = payload.permissions  # already a list or None
    return {"livreur_id": livreur_id, "permissions": perms}
