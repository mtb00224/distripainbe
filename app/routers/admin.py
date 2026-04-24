"""Panneau d'administration de la plateforme DistriPain.

Auth:
  POST /admin/auth/setup   — Créer le compte admin initial
  POST /admin/auth/login   — Connexion admin

Stats:
  GET /admin/stats

Livreurs:
  GET    /admin/livreurs
  GET    /admin/livreurs/{id}
  PATCH  /admin/livreurs/{id}           — Activer/désactiver
  GET    /admin/livreurs/{id}/permissions
  PUT    /admin/livreurs/{id}/permissions

Traffic:
  GET    /admin/traffic
  GET    /admin/traffic/stats
  DELETE /admin/traffic/{id}

Formules abonnement:
  GET/POST   /admin/formules-abonnement
  PUT/DELETE /admin/formules-abonnement/{id}

Abonnements:
  GET  /admin/abonnements
  POST /admin/abonnements/{id}/paiements/{pid}/valider

Moyens de paiement:
  GET/POST   /admin/moyens-paiement
  PUT/DELETE /admin/moyens-paiement/{id}
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import pydantic
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models.abonnement import (
    Abonnement, FormulaAbonnement, MoyenPaiement, PaiementAbonnement
)
from app.models.boulangerie import AdminBoulangerie, Boulangerie
from app.models.client import Client
from app.models.encaissement import Encaissement
from app.models.livreur import AcolyteLivreur, Livreur
from app.models.tournee import Tournee
from app.models.user import User, UserRole, UserSession
from app.schemas.abonnement import (
    AbonnementResponse,
    FormulaAbonnementCreate,
    FormulaAbonnementResponse,
    FormulaAbonnementUpdate,
    PaiementAbonnementResponse,
    ValiderPaiementRequest,
)
from app.schemas.admin import (
    AdminLoginRequest,
    AdminSetupRequest,
    AdminTokenResponse,
    DeviceBreakdown,
    LivreurDetailStats,
    LivreurPerformance,
    LivreurPermissionsUpdate,
    LivreurToggleRequest,
    PlatformBreakdown,
    PlatformStats,
    TrafficEntry,
    TrafficStats,
)
from app.schemas.moyen_paiement import (
    MoyenPaiementCreate,
    MoyenPaiementResponse,
    MoyenPaiementUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])
bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Admin JWT helpers
# ---------------------------------------------------------------------------

def _create_admin_token(user_id: int) -> str:
    return create_access_token({"sub": str(user_id), "role": "admin"})


async def _get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Accès réservé aux admins")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    result = await db.execute(
        select(User).where(User.id == user_id, User.role == UserRole.ADMIN, User.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin introuvable")
    return admin


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/setup", response_model=AdminTokenResponse, status_code=status.HTTP_201_CREATED)
async def setup_admin(payload: AdminSetupRequest, db: AsyncSession = Depends(get_db)):
    """Crée le compte admin plateforme. Ne peut être appelé qu'une seule fois."""
    if payload.setup_key != settings.ADMIN_SETUP_KEY:
        raise HTTPException(status_code=403, detail="Clé de configuration invalide")

    existing = await db.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Un compte admin existe déjà")

    # Vérifier unicité email/username
    if payload.email:
        ex_email = await db.execute(select(User).where(User.email == payload.email))
        if ex_email.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email déjà utilisé")
    ex_user = await db.execute(select(User).where(User.username == payload.username))
    if ex_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")

    admin = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=payload.email,
        phone_number="",
        role=UserRole.ADMIN,
        password_hash=hash_password(payload.password),
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return AdminTokenResponse(access_token=_create_admin_token(admin.id))


@router.post("/auth/login", response_model=AdminTokenResponse)
async def login_admin(payload: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.email == payload.email, User.role == UserRole.ADMIN)
    )
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    return AdminTokenResponse(access_token=_create_admin_token(admin.id))


class _ForgotPasswordCheck(pydantic.BaseModel):
    email: str


class _ForgotPasswordReset(pydantic.BaseModel):
    email: str
    new_password: str


@router.post("/auth/forgot-password/check", status_code=200)
async def admin_forgot_password_check(
    payload: _ForgotPasswordCheck,
    db: AsyncSession = Depends(get_db),
):
    """Vérifie qu'un email admin existe."""
    result = await db.execute(
        select(User).where(User.email == payload.email, User.role == UserRole.ADMIN, User.is_active == True)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Aucun compte administrateur trouvé avec cet email")
    return {"ok": True}


@router.post("/auth/forgot-password/reset", status_code=204)
async def admin_forgot_password_reset(
    payload: _ForgotPasswordReset,
    db: AsyncSession = Depends(get_db),
):
    """Réinitialise le mot de passe d'un admin par email."""
    if len(payload.new_password) < 5:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 5 caractères")
    result = await db.execute(
        select(User).where(User.email == payload.email, User.role == UserRole.ADMIN, User.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="Aucun compte administrateur trouvé avec cet email")
    admin.password_hash = hash_password(payload.new_password)
    await db.commit()


# ---------------------------------------------------------------------------
# Platform stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=PlatformStats)
async def get_platform_stats(
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    since_30d = datetime.now(timezone.utc) - timedelta(days=30)

    r = await db.execute(
        select(func.count()).select_from(Livreur)
        .join(User, Livreur.user_id == User.id)
    )
    total_livreurs = r.scalar_one()

    r = await db.execute(
        select(func.count()).select_from(Livreur)
        .join(User, Livreur.user_id == User.id)
        .where(User.is_active == True)
    )
    active_livreurs = r.scalar_one()

    from app.models.boulangerie import Boulangerie
    r = await db.execute(select(func.count()).select_from(Boulangerie).where(Boulangerie.is_active == True))
    total_boulangeries = r.scalar_one()

    r = await db.execute(select(func.count()).select_from(Tournee))
    total_tournees = r.scalar_one()

    r = await db.execute(select(func.count()).select_from(Client).where(Client.is_active == True))
    total_clients = r.scalar_one()

    r = await db.execute(select(func.count()).select_from(UserSession))
    sessions_total = r.scalar_one()

    r = await db.execute(
        select(func.count()).select_from(UserSession)
        .where(UserSession.logged_in_at >= since_30d)
    )
    sessions_30d = r.scalar_one()

    r = await db.execute(
        select(UserSession.device_type, func.count().label("cnt"))
        .group_by(UserSession.device_type)
    )
    device_counts = {row.device_type: row.cnt for row in r.all()}

    r = await db.execute(
        select(UserSession.platform, func.count().label("cnt"))
        .group_by(UserSession.platform)
    )
    platform_counts = {row.platform: row.cnt for row in r.all()}

    return PlatformStats(
        total_livreurs=total_livreurs,
        active_livreurs=active_livreurs,
        total_boulangeries=total_boulangeries,
        total_tournees=total_tournees,
        total_clients=total_clients,
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
            other=sum(
                v for k, v in platform_counts.items()
                if k not in ("iOS", "Android", "Windows", "macOS", "Linux")
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Livreurs management
# ---------------------------------------------------------------------------

async def _build_livreur_perf(db: AsyncSession, livreur: Livreur, user: User) -> LivreurPerformance:
    since_30d = datetime.now(timezone.utc) - timedelta(days=30)

    r = await db.execute(
        select(func.count()).select_from(Client)
        .where(Client.livreur_id == livreur.id, Client.is_active == True)
    )
    nb_clients = r.scalar_one()

    r = await db.execute(
        select(func.count()).select_from(Tournee).where(Tournee.livreur_id == livreur.id)
    )
    nb_tournees_total = r.scalar_one()

    r = await db.execute(
        select(func.count()).select_from(Tournee)
        .where(Tournee.livreur_id == livreur.id, Tournee.created_at >= since_30d)
    )
    nb_tournees_30d = r.scalar_one()

    r = await db.execute(
        select(func.coalesce(func.sum(Tournee.nb_pains_ecoules), 0))
        .where(Tournee.livreur_id == livreur.id)
    )
    nb_pains_total = int(r.scalar_one())

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

    r = await db.execute(
        select(func.max(Tournee.created_at)).where(Tournee.livreur_id == livreur.id)
    )
    last_activity = r.scalar_one()

    r = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user.id)
        .order_by(UserSession.logged_in_at.desc())
        .limit(1)
    )
    last_session = r.scalar_one_or_none()

    r = await db.execute(
        select(func.count()).select_from(AcolyteLivreur)
        .where(AcolyteLivreur.livreur_principal_id == livreur.id, AcolyteLivreur.is_active == True)
    )
    nb_acolytes = r.scalar_one()

    return LivreurPerformance(
        id=livreur.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone_number=user.phone_number,
        is_active=user.is_active,
        created_at=user.created_at,
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
    )


@router.get("/livreurs", response_model=list[LivreurPerformance])
async def list_livreurs(
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Livreur)
        .options(selectinload(Livreur.user))
        .join(User, Livreur.user_id == User.id)
        .order_by(User.created_at.desc())
    )
    livreurs = result.scalars().all()
    return [await _build_livreur_perf(db, lv, lv.user) for lv in livreurs]


@router.get("/livreurs/{livreur_id}", response_model=LivreurDetailStats)
async def get_livreur_detail(
    livreur_id: int,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Livreur)
        .options(selectinload(Livreur.user))
        .where(Livreur.id == livreur_id)
    )
    livreur = result.scalar_one_or_none()
    if not livreur:
        raise HTTPException(status_code=404, detail="Livreur introuvable")

    perf = await _build_livreur_perf(db, livreur, livreur.user)

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

    r = await db.execute(
        select(UserSession.device_type, func.count().label("cnt"))
        .where(UserSession.user_id == livreur.user_id)
        .group_by(UserSession.device_type)
    )
    device_counts = {row.device_type: row.cnt for row in r.all()}

    r = await db.execute(
        select(UserSession.platform, func.count().label("cnt"))
        .where(UserSession.user_id == livreur.user_id)
        .group_by(UserSession.platform)
    )
    platform_counts = {row.platform: row.cnt for row in r.all()}

    r = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == livreur.user_id)
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
            other=sum(
                v for k, v in platform_counts.items()
                if k not in ("iOS", "Android", "Windows", "macOS", "Linux")
            ),
        ),
        recent_sessions=recent_sessions,
    )


@router.patch("/livreurs/{livreur_id}", response_model=LivreurPerformance)
async def toggle_livreur(
    livreur_id: int,
    payload: LivreurToggleRequest,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Livreur).options(selectinload(Livreur.user)).where(Livreur.id == livreur_id)
    )
    livreur = result.scalar_one_or_none()
    if not livreur:
        raise HTTPException(status_code=404, detail="Livreur introuvable")
    livreur.user.is_active = payload.is_active
    db.add(livreur.user)
    await db.commit()
    return await _build_livreur_perf(db, livreur, livreur.user)


# ---------------------------------------------------------------------------
# Traffic / sessions
# ---------------------------------------------------------------------------

@router.get("/traffic/stats", response_model=TrafficStats)
async def get_traffic_stats(
    _admin: User = Depends(_get_current_admin),
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


@router.get("/traffic", response_model=list[TrafficEntry])
async def get_traffic(
    limit: int = 100,
    offset: int = 0,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(UserSession, User.username, User.role)
        .join(User, User.id == UserSession.user_id)
        .order_by(UserSession.logged_in_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(q)
    rows = result.all()
    return [
        TrafficEntry(
            id=s.id,
            logged_in_at=s.logged_in_at,
            user_id=s.user_id,
            username=username,
            role=role,
            ip_address=s.ip_address,
            device_type=s.device_type,
            platform=s.platform,
            browser=s.browser,
        )
        for s, username, role in rows
    ]


@router.delete("/traffic/{session_id}", status_code=204)
async def delete_traffic_session(
    session_id: int,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(UserSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    await db.delete(session)
    await db.commit()


# ---------------------------------------------------------------------------
# Formules abonnement
# ---------------------------------------------------------------------------

@router.get("/formules-abonnement", response_model=list[FormulaAbonnementResponse])
async def list_formules(
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FormulaAbonnement).order_by(FormulaAbonnement.duree_mois)
    )
    return result.scalars().all()


@router.post(
    "/formules-abonnement",
    response_model=FormulaAbonnementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_formule(
    payload: FormulaAbonnementCreate,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    formule = FormulaAbonnement(**payload.model_dump())
    db.add(formule)
    await db.commit()
    await db.refresh(formule)
    return formule


@router.put("/formules-abonnement/{formule_id}", response_model=FormulaAbonnementResponse)
async def update_formule(
    formule_id: int,
    payload: FormulaAbonnementUpdate,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    formule = await db.get(FormulaAbonnement, formule_id)
    if not formule:
        raise HTTPException(status_code=404, detail="Formule introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(formule, field, value)
    db.add(formule)
    await db.commit()
    await db.refresh(formule)
    return formule


@router.delete("/formules-abonnement/{formule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_formule(
    formule_id: int,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    formule = await db.get(FormulaAbonnement, formule_id)
    if not formule:
        raise HTTPException(status_code=404, detail="Formule introuvable")
    await db.delete(formule)
    await db.commit()


# ---------------------------------------------------------------------------
# Abonnements (vue admin)
# ---------------------------------------------------------------------------

def _build_abonnement_response(a: Abonnement) -> AbonnementResponse:
    formule = FormulaAbonnementResponse(
        id=a.formule.id,
        nom=a.formule.nom,
        cible=a.formule.cible,
        duree_mois=a.formule.duree_mois,
        prix=float(a.formule.prix),
        max_boulangeries=a.formule.max_boulangeries,
        description=a.formule.description,
        is_active=a.formule.is_active,
        created_at=a.formule.created_at,
    )
    paiements = [
        PaiementAbonnementResponse(
            id=p.id,
            abonnement_id=p.abonnement_id,
            montant=p.montant,
            reference=p.reference,
            statut=p.statut,
            date_paiement=p.date_paiement,
            valide_par_id=p.valide_par_id,
        )
        for p in a.paiements
    ]
    return AbonnementResponse(
        id=a.id,
        livreur_id=a.livreur_id,
        boulangerie_id=a.boulangerie_id,
        formule_id=a.formule_id,
        formule=formule,
        date_debut=a.date_debut,
        date_fin=a.date_fin,
        statut=a.statut,
        created_at=a.created_at,
        paiements=paiements,
    )


@router.get("/abonnements", response_model=list[AbonnementResponse])
async def list_abonnements(
    livreur_id: Optional[int] = None,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Abonnement)
        .options(
            selectinload(Abonnement.formule),
            selectinload(Abonnement.paiements),
        )
        .order_by(Abonnement.created_at.desc())
    )
    if livreur_id:
        q = q.where(Abonnement.livreur_id == livreur_id)
    result = await db.execute(q)
    return [_build_abonnement_response(a) for a in result.scalars().all()]


@router.post(
    "/abonnements/{abonnement_id}/paiements/{paiement_id}/valider",
    response_model=AbonnementResponse,
)
async def valider_paiement(
    abonnement_id: int,
    paiement_id: int,
    payload: ValiderPaiementRequest,
    admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
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
    if payload.statut.value == "valide":
        paiement.date_validation = datetime.now(timezone.utc)
        paiement.valide_par_id = admin.id
        abo = await db.get(Abonnement, abonnement_id)
        if abo:
            abo.statut = "actif"
            db.add(abo)

    db.add(paiement)
    await db.commit()

    result = await db.execute(
        select(Abonnement)
        .options(selectinload(Abonnement.formule), selectinload(Abonnement.paiements))
        .where(Abonnement.id == abonnement_id)
    )
    return _build_abonnement_response(result.scalar_one())


# ---------------------------------------------------------------------------
# Moyens de paiement
# ---------------------------------------------------------------------------

@router.get("/moyens-paiement", response_model=list[MoyenPaiementResponse])
async def list_moyens_paiement(
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MoyenPaiement).where(MoyenPaiement.is_active == True).order_by(MoyenPaiement.nom)
    )
    return result.scalars().all()


@router.post(
    "/moyens-paiement",
    response_model=MoyenPaiementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_moyen_paiement(
    payload: MoyenPaiementCreate,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    moyen = MoyenPaiement(**payload.model_dump())
    db.add(moyen)
    await db.commit()
    await db.refresh(moyen)
    return moyen


@router.put("/moyens-paiement/{moyen_id}", response_model=MoyenPaiementResponse)
async def update_moyen_paiement(
    moyen_id: int,
    payload: MoyenPaiementUpdate,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    moyen = await db.get(MoyenPaiement, moyen_id)
    if not moyen:
        raise HTTPException(status_code=404, detail="Moyen de paiement introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(moyen, field, value)
    db.add(moyen)
    await db.commit()
    await db.refresh(moyen)
    return moyen


@router.delete("/moyens-paiement/{moyen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_moyen_paiement(
    moyen_id: int,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    moyen = await db.get(MoyenPaiement, moyen_id)
    if not moyen:
        raise HTTPException(status_code=404, detail="Moyen de paiement introuvable")
    await db.delete(moyen)
    await db.commit()


# ---------------------------------------------------------------------------
# Permissions livreur
# ---------------------------------------------------------------------------

@router.get("/livreurs/{livreur_id}/permissions")
async def get_livreur_permissions(
    livreur_id: int,
    _admin: User = Depends(_get_current_admin),
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
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    livreur = await db.get(Livreur, livreur_id)
    if not livreur:
        raise HTTPException(status_code=404, detail="Livreur introuvable")
    livreur.permissions = (
        json.dumps(payload.permissions) if payload.permissions is not None else None
    )
    db.add(livreur)
    await db.commit()
    return {"livreur_id": livreur_id, "permissions": payload.permissions}


# ---------------------------------------------------------------------------
# Boulangeries (vue admin plateforme)
# ---------------------------------------------------------------------------

@router.get("/boulangeries")
async def list_admin_boulangeries(
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Liste toutes les boulangeries de la plateforme."""
    result = await db.execute(
        select(Boulangerie)
        .options(selectinload(Boulangerie.admin_boulangerie).selectinload(AdminBoulangerie.user))
        .order_by(Boulangerie.created_at.desc())
    )
    boulangeries = result.scalars().all()
    return [
        {
            "id": b.id,
            "nom": b.nom,
            "contact": b.contact,
            "address": b.address,
            "is_active": b.is_active,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "admin_nom": (
                f"{b.admin_boulangerie.user.first_name} {b.admin_boulangerie.user.last_name}"
                if b.admin_boulangerie and b.admin_boulangerie.user else None
            ),
            "admin_email": (
                b.admin_boulangerie.user.email
                if b.admin_boulangerie and b.admin_boulangerie.user else None
            ),
        }
        for b in boulangeries
    ]


@router.get("/admins-boulangerie")
async def list_admins_boulangerie(
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Liste tous les comptes admin boulangerie."""
    result = await db.execute(
        select(AdminBoulangerie)
        .options(
            selectinload(AdminBoulangerie.user),
            selectinload(AdminBoulangerie.boulangeries),
        )
    )
    admins = result.scalars().all()
    return [
        {
            "id": ab.id,
            "user_id": ab.user_id,
            "first_name": ab.user.first_name if ab.user else "",
            "last_name": ab.user.last_name if ab.user else "",
            "email": ab.user.email if ab.user else None,
            "phone_number": ab.user.phone_number if ab.user else None,
            "is_active": ab.user.is_active if ab.user else False,
            "nb_boulangeries": len(ab.boulangeries),
            "created_at": ab.user.created_at.isoformat() if ab.user and ab.user.created_at else None,
        }
        for ab in admins
    ]


@router.patch("/admins-boulangerie/{admin_b_id}")
async def toggle_admin_boulangerie(
    admin_b_id: int,
    payload: dict,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Activer/désactiver un compte admin boulangerie."""
    ab = await db.get(AdminBoulangerie, admin_b_id, options=[selectinload(AdminBoulangerie.user)])
    if not ab:
        raise HTTPException(status_code=404, detail="Admin boulangerie introuvable")
    if "is_active" in payload:
        ab.user.is_active = payload["is_active"]
        db.add(ab.user)
        await db.commit()
    return {"id": ab.id, "is_active": ab.user.is_active}


# ---------------------------------------------------------------------------
# Détail gérant boulangerie
# ---------------------------------------------------------------------------

@router.get("/admins-boulangerie/{admin_b_id}/detail")
async def get_admin_boulangerie_detail(
    admin_b_id: int,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.models.production import SessionProduction, DistributionLivreur
    from app.models.boulangerie import Depense

    ab = await db.get(
        AdminBoulangerie, admin_b_id,
        options=[
            selectinload(AdminBoulangerie.user),
            selectinload(AdminBoulangerie.boulangeries),
        ]
    )
    if not ab:
        raise HTTPException(status_code=404, detail="Gérant introuvable")

    boulangeries_detail = []
    for b in ab.boulangeries:
        # Sessions
        sess_result = await db.execute(
            select(SessionProduction).where(SessionProduction.boulangerie_id == b.id)
        )
        sessions = sess_result.scalars().all()
        session_ids = [s.id for s in sessions]
        nb_pains = sum(s.nb_pains_produits for s in sessions)
        montant_ambulatoire = float(sum(s.montant_ambulatoire or 0 for s in sessions))

        montant_enc = montant_ambulatoire
        if session_ids:
            dist_result = await db.execute(
                select(DistributionLivreur).where(DistributionLivreur.session_id.in_(session_ids))
            )
            montant_enc += float(sum(d.montant_encaisse or 0 for d in dist_result.scalars().all()))

        # Dépenses
        dep_result = await db.execute(select(Depense).where(Depense.boulangerie_id == b.id))
        total_dep = float(sum(d.quantite * d.prix_unitaire for d in dep_result.scalars().all()))

        boulangeries_detail.append({
            "id": b.id,
            "nom": b.nom,
            "contact": b.contact,
            "address": b.address,
            "is_active": b.is_active,
            "nb_sessions": len(sessions),
            "nb_pains_produits": nb_pains,
            "montant_encaisse": montant_enc,
            "total_depenses": total_dep,
            "benefice_net": montant_enc - total_dep,
        })

    global_enc = sum(b["montant_encaisse"] for b in boulangeries_detail)
    global_dep = sum(b["total_depenses"] for b in boulangeries_detail)

    return {
        "id": ab.id,
        "first_name": ab.user.first_name,
        "last_name": ab.user.last_name,
        "email": ab.user.email,
        "phone_number": ab.user.phone_number,
        "is_active": ab.user.is_active,
        "nb_boulangeries": len(ab.boulangeries),
        "montant_encaisse_global": global_enc,
        "total_depenses_global": global_dep,
        "benefice_net_global": global_enc - global_dep,
        "boulangeries": boulangeries_detail,
    }


# ---------------------------------------------------------------------------
# Détail boulangerie
# ---------------------------------------------------------------------------

@router.get("/boulangeries/{boulangerie_id}/detail")
async def get_boulangerie_detail(
    boulangerie_id: int,
    _admin: User = Depends(_get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.models.production import SessionProduction, DistributionLivreur
    from app.models.boulangerie import Depense, StaffBoulangerie

    b = await db.get(
        Boulangerie, boulangerie_id,
        options=[
            selectinload(Boulangerie.admin_boulangerie).selectinload(AdminBoulangerie.user),
        ]
    )
    if not b:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")

    # Staff
    staff_result = await db.execute(
        select(StaffBoulangerie)
        .options(selectinload(StaffBoulangerie.user))
        .where(StaffBoulangerie.boulangerie_id == boulangerie_id, StaffBoulangerie.is_active == True)
    )
    staff_list = [
        {
            "id": s.id,
            "prenom": s.user.first_name if s.user else "",
            "nom": s.user.last_name if s.user else "",
            "role": s.role_interne.value if s.role_interne else "",
        }
        for s in staff_result.scalars().all()
    ]

    # Sessions
    sess_result = await db.execute(
        select(SessionProduction).where(SessionProduction.boulangerie_id == boulangerie_id)
    )
    sessions = sess_result.scalars().all()
    session_ids = [s.id for s in sessions]
    nb_pains = sum(s.nb_pains_produits for s in sessions)
    montant_ambulatoire = float(sum(s.montant_ambulatoire or 0 for s in sessions))

    montant_enc = montant_ambulatoire
    nb_pains_vendus = 0
    if session_ids:
        dist_result = await db.execute(
            select(DistributionLivreur).where(DistributionLivreur.session_id.in_(session_ids))
        )
        dists = dist_result.scalars().all()
        montant_enc += float(sum(d.montant_encaisse or 0 for d in dists))
        nb_pains_vendus = sum(d.nb_pains_donnes - (d.nb_pains_retournes or 0) for d in dists)

    # Dépenses
    dep_result = await db.execute(
        select(Depense)
        .options(selectinload(Depense.categorie))
        .where(Depense.boulangerie_id == boulangerie_id)
        .order_by(Depense.date_enregistrement.desc())
        .limit(10)
    )
    depenses_list = []
    total_dep = 0.0
    all_dep = await db.execute(select(Depense).where(Depense.boulangerie_id == boulangerie_id))
    for d in all_dep.scalars().all():
        total_dep += float(d.quantite * d.prix_unitaire)
    for d in dep_result.scalars().all():
        depenses_list.append({
            "motif": d.motif,
            "categorie": d.categorie.nom if d.categorie else "",
            "montant": float(d.quantite * d.prix_unitaire),
            "date": d.date_enregistrement.strftime("%d/%m/%Y"),
        })

    return {
        "id": b.id,
        "nom": b.nom,
        "contact": b.contact,
        "address": b.address,
        "is_active": b.is_active,
        "admin_nom": (
            f"{b.admin_boulangerie.user.first_name} {b.admin_boulangerie.user.last_name}"
            if b.admin_boulangerie and b.admin_boulangerie.user else None
        ),
        "nb_staff": len(staff_list),
        "staff": staff_list,
        "nb_sessions": len(sessions),
        "nb_pains_produits": nb_pains,
        "nb_pains_vendus": nb_pains_vendus,
        "montant_encaisse": montant_enc,
        "total_depenses": total_dep,
        "benefice_net": montant_enc - total_dep,
        "dernieres_depenses": depenses_list,
    }
