"""
Portions de pain par livreur interne.

GET    /admin-boulangerie/livreurs-internes/{id}/portions
POST   /admin-boulangerie/livreurs-internes/{id}/portions
PUT    /admin-boulangerie/livreurs-internes/{id}/portions/{portion_id}
DELETE /admin-boulangerie/livreurs-internes/{id}/portions/{portion_id}
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.boulangerie import AdminBoulangerie, Boulangerie
from app.models.livreur_interne import LivreurInterne
from app.models.livreur_interne_portion import LivreurInternePortionPain
from app.routers.admin_boulangerie import _get_current_admin_boulangerie

router = APIRouter(
    prefix="/admin-boulangerie/livreurs-internes",
    tags=["livreur-interne-portions"],
)


# ── Schemas inline ────────────────────────────────────────────────────────────

class PortionLivreurCreate(BaseModel):
    nom: str
    prix_achat: Decimal
    equivalent_pains: Decimal


class PortionLivreurUpdate(BaseModel):
    nom: Optional[str] = None
    prix_achat: Optional[Decimal] = None
    equivalent_pains: Optional[Decimal] = None
    is_active: Optional[bool] = None


class PortionLivreurResponse(BaseModel):
    id: int
    livreur_interne_id: int
    nom: str
    prix_achat: Decimal
    equivalent_pains: Decimal
    is_active: bool

    class Config:
        from_attributes = True


# ── Helper ────────────────────────────────────────────────────────────────────

async def _owned_livreur_interne(
    livreur_interne_id: int,
    admin_b: AdminBoulangerie,
    db: AsyncSession,
) -> LivreurInterne:
    result = await db.execute(
        select(LivreurInterne)
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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{livreur_interne_id}/portions", response_model=list[PortionLivreurResponse])
async def list_portions(
    livreur_interne_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    await _owned_livreur_interne(livreur_interne_id, admin_b, db)
    result = await db.execute(
        select(LivreurInternePortionPain)
        .where(LivreurInternePortionPain.livreur_interne_id == livreur_interne_id)
        .order_by(LivreurInternePortionPain.nom)
    )
    return result.scalars().all()


@router.post("/{livreur_interne_id}/portions", response_model=PortionLivreurResponse, status_code=status.HTTP_201_CREATED)
async def create_portion(
    livreur_interne_id: int,
    payload: PortionLivreurCreate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    await _owned_livreur_interne(livreur_interne_id, admin_b, db)
    portion = LivreurInternePortionPain(
        livreur_interne_id=livreur_interne_id,
        nom=payload.nom,
        prix_achat=payload.prix_achat,
        equivalent_pains=payload.equivalent_pains,
    )
    db.add(portion)
    await db.commit()
    await db.refresh(portion)
    return portion


@router.put("/{livreur_interne_id}/portions/{portion_id}", response_model=PortionLivreurResponse)
async def update_portion(
    livreur_interne_id: int,
    portion_id: int,
    payload: PortionLivreurUpdate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    await _owned_livreur_interne(livreur_interne_id, admin_b, db)
    result = await db.execute(
        select(LivreurInternePortionPain).where(
            LivreurInternePortionPain.id == portion_id,
            LivreurInternePortionPain.livreur_interne_id == livreur_interne_id,
        )
    )
    portion = result.scalar_one_or_none()
    if not portion:
        raise HTTPException(status_code=404, detail="Portion introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(portion, field, value)
    db.add(portion)
    await db.commit()
    await db.refresh(portion)
    return portion


@router.delete("/{livreur_interne_id}/portions/{portion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portion(
    livreur_interne_id: int,
    portion_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    await _owned_livreur_interne(livreur_interne_id, admin_b, db)
    result = await db.execute(
        select(LivreurInternePortionPain).where(
            LivreurInternePortionPain.id == portion_id,
            LivreurInternePortionPain.livreur_interne_id == livreur_interne_id,
        )
    )
    portion = result.scalar_one_or_none()
    if not portion:
        raise HTTPException(status_code=404, detail="Portion introuvable")
    await db.delete(portion)
    await db.commit()
