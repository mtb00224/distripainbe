"""
Gestion des livreurs internes d'une boulangerie.

GET    /admin-boulangerie/livreurs-internes           — Liste
POST   /admin-boulangerie/livreurs-internes           — Créer
GET    /admin-boulangerie/livreurs-internes/{id}      — Détail
PUT    /admin-boulangerie/livreurs-internes/{id}      — Modifier
DELETE /admin-boulangerie/livreurs-internes/{id}      — Désactiver

GET    /admin-boulangerie/livreurs-internes/{id}/compte          — Solde du compte interne
POST   /admin-boulangerie/livreurs-internes/{id}/compte/retrait  — Enregistrer un retrait
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.boulangerie import AdminBoulangerie, Boulangerie
from app.models.livreur_interne import CompteInterneLivreur, LivreurInterne, RetirementCompte
from app.routers.admin_boulangerie import _get_current_admin_boulangerie
from app.schemas.livreur_interne import (
    CompteInterneResponse,
    LivreurInterneCreate,
    LivreurInterneResponse,
    LivreurInterneUpdate,
    RetraitCreate,
    RetraitResponse,
)

router = APIRouter(prefix="/admin-boulangerie/livreurs-internes", tags=["livreurs-internes"])


def _build_response(li: LivreurInterne) -> LivreurInterneResponse:
    solde = li.compte_interne.solde_actuel if li.compte_interne else None
    return LivreurInterneResponse(
        id=li.id,
        boulangerie_id=li.boulangerie_id,
        prenom=li.prenom,
        nom=li.nom,
        telephone=li.telephone,
        prix_achat_pain=li.prix_achat_pain,
        user_id=li.user_id,
        is_active=li.is_active,
        created_at=li.created_at,
        solde_compte=solde,
    )


async def _get_livreur_interne(
    livreur_interne_id: int,
    context: tuple[AdminBoulangerie, Optional[int]],
    db: AsyncSession,
) -> LivreurInterne:
    admin_b, boulangerie_active_id = context
    result = await db.execute(
        select(LivreurInterne)
        .options(selectinload(LivreurInterne.compte_interne))
        .join(Boulangerie, Boulangerie.id == LivreurInterne.boulangerie_id)
        .where(
            LivreurInterne.id == livreur_interne_id,
            Boulangerie.admin_boulangerie_id == admin_b.id,
        )
    )
    li = result.scalar_one_or_none()
    if not li:
        raise HTTPException(status_code=404, detail="Livreur interne introuvable")
    return li


# ─────────────────────────────────────────────
# CRUD livreur interne
# ─────────────────────────────────────────────

@router.get("", response_model=list[LivreurInterneResponse])
async def list_livreurs_internes(
    boulangerie_id: Optional[int] = None,
    include_inactive: bool = False,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, boulangerie_active_id = context

    stmt = (
        select(LivreurInterne)
        .options(selectinload(LivreurInterne.compte_interne))
        .join(Boulangerie, Boulangerie.id == LivreurInterne.boulangerie_id)
        .where(Boulangerie.admin_boulangerie_id == admin_b.id)
    )

    # Filtrer par boulangerie spécifique si fourni, sinon boulangerie active
    target_id = boulangerie_id or boulangerie_active_id
    if target_id:
        stmt = stmt.where(LivreurInterne.boulangerie_id == target_id)

    if not include_inactive:
        stmt = stmt.where(LivreurInterne.is_active == True)

    result = await db.execute(stmt.order_by(LivreurInterne.nom, LivreurInterne.prenom))
    return [_build_response(li) for li in result.scalars().all()]


@router.post("", response_model=list[LivreurInterneResponse], status_code=status.HTTP_201_CREATED)
async def create_livreur_interne(
    payload: LivreurInterneCreate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context

    if not payload.boulangerie_ids:
        raise HTTPException(status_code=400, detail="Sélectionnez au moins une boulangerie")

    admin_boulangerie_ids = {b.id for b in admin_b.boulangeries}
    invalid = [bid for bid in payload.boulangerie_ids if bid not in admin_boulangerie_ids]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Boulangeries non autorisées : {invalid}")

    created_ids = []
    for bid in payload.boulangerie_ids:
        li = LivreurInterne(
            boulangerie_id=bid,
            prenom=payload.prenom,
            nom=payload.nom,
            telephone=payload.telephone,
            prix_achat_pain=payload.prix_achat_pain,
        )
        db.add(li)
        await db.flush()
        created_ids.append(li.id)

    await db.commit()

    result = await db.execute(
        select(LivreurInterne)
        .options(selectinload(LivreurInterne.compte_interne))
        .where(LivreurInterne.id.in_(created_ids))
    )
    return [_build_response(li) for li in result.scalars().all()]


@router.get("/{livreur_interne_id}", response_model=LivreurInterneResponse)
async def get_livreur_interne(
    livreur_interne_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    li = await _get_livreur_interne(livreur_interne_id, context, db)
    return _build_response(li)


@router.put("/{livreur_interne_id}", response_model=LivreurInterneResponse)
async def update_livreur_interne(
    livreur_interne_id: int,
    payload: LivreurInterneUpdate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    li = await _get_livreur_interne(livreur_interne_id, context, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(li, field, value)
    db.add(li)
    await db.commit()
    # Re-fetch avec selectinload pour éviter le lazy-load async
    result = await db.execute(
        select(LivreurInterne)
        .options(selectinload(LivreurInterne.compte_interne))
        .where(LivreurInterne.id == livreur_interne_id)
    )
    return _build_response(result.scalar_one())


@router.delete("/{livreur_interne_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_livreur_interne(
    livreur_interne_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    li = await _get_livreur_interne(livreur_interne_id, context, db)
    li.is_active = False
    db.add(li)
    await db.commit()


# ─────────────────────────────────────────────
# Compte interne
# ─────────────────────────────────────────────

@router.get("/{livreur_interne_id}/compte", response_model=CompteInterneResponse)
async def get_compte_interne(
    livreur_interne_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    li = await _get_livreur_interne(livreur_interne_id, context, db)
    if not li.compte_interne:
        raise HTTPException(status_code=404, detail="Ce livreur n'a pas de compte interne")
    return li.compte_interne


@router.post("/{livreur_interne_id}/compte/retrait", response_model=RetraitResponse, status_code=201)
async def retrait_compte_interne(
    livreur_interne_id: int,
    payload: RetraitCreate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    li = await _get_livreur_interne(livreur_interne_id, context, db)

    if not li.compte_interne:
        raise HTTPException(status_code=404, detail="Ce livreur n'a pas de compte interne")
    if li.compte_interne.solde_actuel < payload.montant:
        raise HTTPException(status_code=400, detail="Solde insuffisant")

    li.compte_interne.solde_actuel -= payload.montant
    retrait = RetirementCompte(
        compte_id=li.compte_interne.id,
        montant=payload.montant,
        notes=payload.notes,
        created_by_id=admin_b.user_id,
    )
    db.add(retrait)
    db.add(li.compte_interne)
    await db.commit()
    await db.refresh(retrait)
    return retrait
