"""Router AdminBoulangerie — gestion des boulangeries par leur propriétaire.

Auth:
  POST /admin-boulangerie/auth/register   — Inscription
  POST /admin-boulangerie/auth/login      — Connexion
  POST /admin-boulangerie/auth/switch/{id} — Changer de boulangerie active

Mes boulangeries:
  GET    /admin-boulangerie/boulangeries          — Liste toutes ses boulangeries
  POST   /admin-boulangerie/boulangeries          — Créer une nouvelle boulangerie
  GET    /admin-boulangerie/boulangeries/{id}     — Détails
  PUT    /admin-boulangerie/boulangeries/{id}     — Modifier
  DELETE /admin-boulangerie/boulangeries/{id}     — Désactiver

Staff (dans la boulangerie active):
  GET    /admin-boulangerie/staff                 — Liste le staff
  POST   /admin-boulangerie/staff                 — Ajouter un membre
  PUT    /admin-boulangerie/staff/{id}            — Modifier rôle/statut
  DELETE /admin-boulangerie/staff/{id}            — Retirer du staff

Livreurs liés:
  GET    /admin-boulangerie/livreurs              — Liste les livreurs liés
  POST   /admin-boulangerie/livreurs/link         — Lier un livreur existant
  PUT    /admin-boulangerie/livreurs/{id}/contrat — Modifier contrat (prix, contact)
  DELETE /admin-boulangerie/livreurs/{id}         — Délier un livreur
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pydantic
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models.boulangerie import AdminBoulangerie, Boulangerie, StaffBoulangerie
from app.models.livreur import Livreur, LivreurBoulangerie
from app.models.user import User, UserRole
from app.schemas.admin_boulangerie import (
    AdminBoulangerieProfileResponse,
    BoulangerieCreate,
    BoulangerieResponse,
    BoulangerieUpdate,
    LivreurContratUpdate,
    LivreurLinkRequest,
    LivreurLinkResponse,
    StaffCreate,
    StaffResponse,
    StaffUpdate,
)
from app.schemas.auth import TokenResponse

router = APIRouter(prefix="/admin-boulangerie", tags=["admin-boulangerie"])
bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_ab_token(user_id: int, admin_boulangerie_id: int, boulangerie_active_id: Optional[int]) -> str:
    return create_access_token({
        "sub": str(user_id),
        "role": "admin_boulangerie",
        "admin_boulangerie_id": admin_boulangerie_id,
        "boulangerie_active_id": boulangerie_active_id,
    })


async def _get_current_admin_boulangerie(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> tuple[AdminBoulangerie, Optional[int]]:
    """Retourne (AdminBoulangerie, boulangerie_active_id)."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token manquant")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("role") != "admin_boulangerie":
            raise HTTPException(status_code=403, detail="Accès réservé aux admin boulangerie")
        admin_boulangerie_id = int(payload["admin_boulangerie_id"])
        boulangerie_active_id = payload.get("boulangerie_active_id")
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    result = await db.execute(
        select(AdminBoulangerie)
        .options(selectinload(AdminBoulangerie.user), selectinload(AdminBoulangerie.boulangeries))
        .where(AdminBoulangerie.id == admin_boulangerie_id)
    )
    admin_b = result.scalar_one_or_none()
    if not admin_b or not admin_b.user.is_active:
        raise HTTPException(status_code=401, detail="Compte introuvable ou désactivé")

    return admin_b, boulangerie_active_id


async def _require_active_boulangerie(
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
) -> tuple[AdminBoulangerie, Boulangerie]:
    """Retourne (AdminBoulangerie, Boulangerie active). Lève 400 si aucune boulangerie sélectionnée."""
    admin_b, boulangerie_active_id = context
    if not boulangerie_active_id:
        raise HTTPException(
            status_code=400,
            detail="Aucune boulangerie active sélectionnée. Utilisez /switch/{id}.",
        )
    result = await db.execute(
        select(Boulangerie).where(
            Boulangerie.id == boulangerie_active_id,
            Boulangerie.admin_boulangerie_id == admin_b.id,
        )
    )
    boulangerie = result.scalar_one_or_none()
    if not boulangerie:
        raise HTTPException(status_code=404, detail="Boulangerie active introuvable")
    return admin_b, boulangerie


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.post("/auth/switch/{boulangerie_id}", response_model=TokenResponse)
async def switch_boulangerie(
    boulangerie_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    """Change la boulangerie active dans le token JWT."""
    admin_b, _ = context

    result = await db.execute(
        select(Boulangerie).where(
            Boulangerie.id == boulangerie_id,
            Boulangerie.admin_boulangerie_id == admin_b.id,
            Boulangerie.is_active == True,
        )
    )
    boulangerie = result.scalar_one_or_none()
    if not boulangerie:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable ou inactive")

    return TokenResponse(
        access_token=_create_ab_token(admin_b.user_id, admin_b.id, boulangerie_id),
        role="admin_boulangerie",
        admin_boulangerie_id=admin_b.id,
        boulangerie_active_id=boulangerie_id,
    )


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------

@router.get("/me", response_model=AdminBoulangerieProfileResponse)
async def get_profile(
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
):
    admin_b, _ = context
    return AdminBoulangerieProfileResponse(
        id=admin_b.id,
        first_name=admin_b.user.first_name,
        last_name=admin_b.user.last_name,
        email=admin_b.user.email,
        boulangeries=[
            BoulangerieResponse.model_validate(b)
            for b in admin_b.boulangeries
        ],
    )


class ChangePasswordRequest(pydantic.BaseModel):
    old_password: str
    new_password: str


@router.put("/auth/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    user = await db.get(User, admin_b.user_id)
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if len(payload.new_password) < 5:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit contenir au moins 5 caractères")
    user.password_hash = hash_password(payload.new_password)
    await db.commit()


# ---------------------------------------------------------------------------
# Boulangeries
# ---------------------------------------------------------------------------

@router.get("/boulangeries", response_model=list[BoulangerieResponse])
async def list_boulangeries(
    include_inactive: bool = False,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    stmt = select(Boulangerie).where(Boulangerie.admin_boulangerie_id == admin_b.id)
    if not include_inactive:
        stmt = stmt.where(Boulangerie.is_active == True)
    result = await db.execute(stmt.order_by(Boulangerie.created_at))
    return result.scalars().all()


@router.post("/boulangeries", response_model=BoulangerieResponse, status_code=201)
async def create_boulangerie(
    payload: BoulangerieCreate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    boulangerie = Boulangerie(
        nom=payload.nom,
        contact=payload.contact,
        address=payload.address,
        prix_vente_pain=payload.prix_vente_pain,
        admin_boulangerie_id=admin_b.id,
    )
    db.add(boulangerie)
    await db.commit()
    await db.refresh(boulangerie)
    return boulangerie


@router.get("/boulangeries/{boulangerie_id}", response_model=BoulangerieResponse)
async def get_boulangerie(
    boulangerie_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    result = await db.execute(
        select(Boulangerie).where(
            Boulangerie.id == boulangerie_id,
            Boulangerie.admin_boulangerie_id == admin_b.id,
        )
    )
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")
    return b


@router.put("/boulangeries/{boulangerie_id}", response_model=BoulangerieResponse)
async def update_boulangerie(
    boulangerie_id: int,
    payload: BoulangerieUpdate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    result = await db.execute(
        select(Boulangerie).where(
            Boulangerie.id == boulangerie_id,
            Boulangerie.admin_boulangerie_id == admin_b.id,
        )
    )
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(b, field, value)
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return b


@router.delete("/boulangeries/{boulangerie_id}", status_code=204)
async def deactivate_boulangerie(
    boulangerie_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    result = await db.execute(
        select(Boulangerie).where(
            Boulangerie.id == boulangerie_id,
            Boulangerie.admin_boulangerie_id == admin_b.id,
        )
    )
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")
    b.is_active = False
    db.add(b)
    await db.commit()


# ---------------------------------------------------------------------------
# Staff de la boulangerie active
# ---------------------------------------------------------------------------

def _serialize_staff(s: StaffBoulangerie) -> StaffResponse:
    return StaffResponse(
        id=s.id,
        user_id=s.user_id,
        first_name=s.user.first_name if s.user else "",
        last_name=s.user.last_name if s.user else "",
        username=s.user.username if s.user else "",
        email=s.user.email if s.user else None,
        role_interne=s.role_interne,
        boulangerie_id=s.boulangerie_id,
        is_active=s.is_active,
    )


@router.get("/staff", response_model=list[StaffResponse])
async def list_staff(
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    result = await db.execute(
        select(StaffBoulangerie)
        .options(selectinload(StaffBoulangerie.user))
        .where(
            StaffBoulangerie.boulangerie_id == boulangerie.id,
            StaffBoulangerie.is_active == True,
        )
    )
    return [_serialize_staff(s) for s in result.scalars().all()]


@router.post("/staff", response_model=StaffResponse, status_code=201)
async def add_staff(
    payload: StaffCreate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, boulangerie = context

    ex_u = await db.execute(select(User).where(User.username == payload.username))
    if ex_u.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")
    if payload.email:
        ex_e = await db.execute(select(User).where(User.email == payload.email))
        if ex_e.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email déjà utilisé")

    from app.crud.acolyte import DEFAULT_ACOLYTE_PASSWORD
    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=payload.email,
        phone_number=payload.phone_number or "",
        role=UserRole.STAFF_BOULANGERIE,
        password_hash=hash_password(DEFAULT_ACOLYTE_PASSWORD),
        must_change_password=True,
    )
    db.add(user)
    await db.flush()

    staff = StaffBoulangerie(
        user_id=user.id,
        boulangerie_id=boulangerie.id,
        role_interne=payload.role_interne,
        created_by_id=admin_b.user_id,
    )
    db.add(staff)
    await db.commit()

    result = await db.execute(
        select(StaffBoulangerie)
        .options(selectinload(StaffBoulangerie.user))
        .where(StaffBoulangerie.id == staff.id)
    )
    return _serialize_staff(result.scalar_one())


@router.put("/staff/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: int,
    payload: StaffUpdate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    result = await db.execute(
        select(StaffBoulangerie)
        .options(selectinload(StaffBoulangerie.user))
        .where(StaffBoulangerie.id == staff_id, StaffBoulangerie.boulangerie_id == boulangerie.id)
    )
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Membre du staff introuvable")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(staff, field, value)
    db.add(staff)
    await db.commit()
    await db.refresh(staff)

    result = await db.execute(
        select(StaffBoulangerie)
        .options(selectinload(StaffBoulangerie.user))
        .where(StaffBoulangerie.id == staff.id)
    )
    return _serialize_staff(result.scalar_one())


@router.delete("/staff/{staff_id}", status_code=204)
async def remove_staff(
    staff_id: int,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    result = await db.execute(
        select(StaffBoulangerie).where(
            StaffBoulangerie.id == staff_id,
            StaffBoulangerie.boulangerie_id == boulangerie.id,
        )
    )
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Membre du staff introuvable")
    staff.is_active = False
    db.add(staff)
    await db.commit()


# ---------------------------------------------------------------------------
# Livreurs liés à la boulangerie active
# ---------------------------------------------------------------------------

def _serialize_livreur_link(lb: LivreurBoulangerie) -> LivreurLinkResponse:
    livreur = lb.livreur
    return LivreurLinkResponse(
        livreur_id=livreur.id,
        first_name=livreur.user.first_name if livreur.user else "",
        last_name=livreur.user.last_name if livreur.user else "",
        username=livreur.user.username if livreur.user else "",
        email=livreur.user.email if livreur.user else None,
        prix_achat_pain=lb.prix_achat_pain,
        contact_local=lb.contact_local,
        is_active=lb.is_active,
    )


@router.get("/livreurs", response_model=list[LivreurLinkResponse])
async def list_livreurs(
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    result = await db.execute(
        select(LivreurBoulangerie)
        .options(
            selectinload(LivreurBoulangerie.livreur).selectinload(Livreur.user)
        )
        .where(LivreurBoulangerie.boulangerie_id == boulangerie.id)
    )
    return [_serialize_livreur_link(lb) for lb in result.scalars().all()]


@router.post("/livreurs/link", response_model=LivreurLinkResponse, status_code=201)
async def link_livreur(
    payload: LivreurLinkRequest,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    """Lie un livreur existant (par username ou email) à la boulangerie active."""
    _, boulangerie = context

    # Chercher le User par username ou email
    result = await db.execute(
        select(User).where(
            User.role == UserRole.LIVREUR,
            (User.username == payload.identifier) | (User.email == payload.identifier),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Aucun livreur trouvé avec cet identifiant",
        )

    livreur_result = await db.execute(
        select(Livreur).where(Livreur.user_id == user.id)
    )
    livreur = livreur_result.scalar_one_or_none()
    if not livreur:
        raise HTTPException(status_code=404, detail="Profil livreur introuvable")

    # Vérifier si déjà lié
    existing = await db.execute(
        select(LivreurBoulangerie).where(
            LivreurBoulangerie.livreur_id == livreur.id,
            LivreurBoulangerie.boulangerie_id == boulangerie.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ce livreur est déjà lié à cette boulangerie")

    lb = LivreurBoulangerie(
        livreur_id=livreur.id,
        boulangerie_id=boulangerie.id,
        prix_achat_pain=payload.prix_achat_pain,
        contact_local=payload.contact_local,
    )
    db.add(lb)
    await db.commit()

    result = await db.execute(
        select(LivreurBoulangerie)
        .options(selectinload(LivreurBoulangerie.livreur).selectinload(Livreur.user))
        .where(
            LivreurBoulangerie.livreur_id == livreur.id,
            LivreurBoulangerie.boulangerie_id == boulangerie.id,
        )
    )
    return _serialize_livreur_link(result.scalar_one())


@router.put("/livreurs/{livreur_id}/contrat", response_model=LivreurLinkResponse)
async def update_livreur_contrat(
    livreur_id: int,
    payload: LivreurContratUpdate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    result = await db.execute(
        select(LivreurBoulangerie)
        .options(selectinload(LivreurBoulangerie.livreur).selectinload(Livreur.user))
        .where(
            LivreurBoulangerie.livreur_id == livreur_id,
            LivreurBoulangerie.boulangerie_id == boulangerie.id,
        )
    )
    lb = result.scalar_one_or_none()
    if not lb:
        raise HTTPException(status_code=404, detail="Contrat livreur introuvable")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lb, field, value)
    db.add(lb)
    await db.commit()
    await db.refresh(lb)

    result = await db.execute(
        select(LivreurBoulangerie)
        .options(selectinload(LivreurBoulangerie.livreur).selectinload(Livreur.user))
        .where(
            LivreurBoulangerie.livreur_id == livreur_id,
            LivreurBoulangerie.boulangerie_id == boulangerie.id,
        )
    )
    return _serialize_livreur_link(result.scalar_one())


@router.delete("/livreurs/{livreur_id}", status_code=204)
async def unlink_livreur(
    livreur_id: int,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    """Délie un livreur de la boulangerie active."""
    _, boulangerie = context
    result = await db.execute(
        select(LivreurBoulangerie).where(
            LivreurBoulangerie.livreur_id == livreur_id,
            LivreurBoulangerie.boulangerie_id == boulangerie.id,
        )
    )
    lb = result.scalar_one_or_none()
    if not lb:
        raise HTTPException(status_code=404, detail="Lien livreur-boulangerie introuvable")
    await db.delete(lb)
    await db.commit()
