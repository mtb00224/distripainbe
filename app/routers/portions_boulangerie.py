"""
Configuration des portions de pain pour un admin boulangerie.

GET    /admin-boulangerie/portions-pain          — Liste
POST   /admin-boulangerie/portions-pain          — Créer
PUT    /admin-boulangerie/portions-pain/{id}     — Modifier
DELETE /admin-boulangerie/portions-pain/{id}     — Supprimer
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.boulangerie import AdminBoulangerie, PortionPainBoulangerie
from app.routers.admin_boulangerie import _get_current_admin_boulangerie

router = APIRouter(prefix="/admin-boulangerie/portions-pain", tags=["portions-boulangerie"])


class PortionBoulangerieCreate(BaseModel):
    nom: str
    equivalent_pains: Decimal
    ordre: int = 0


class PortionBoulangerieUpdate(BaseModel):
    nom: Optional[str] = None
    equivalent_pains: Optional[Decimal] = None
    ordre: Optional[int] = None


class PortionBoulangerieResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    equivalent_pains: Decimal
    ordre: int


@router.get("", response_model=list[PortionBoulangerieResponse])
async def list_portions(
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    result = await db.execute(
        select(PortionPainBoulangerie)
        .where(PortionPainBoulangerie.admin_boulangerie_id == admin_b.id)
        .order_by(PortionPainBoulangerie.ordre, PortionPainBoulangerie.nom)
    )
    return result.scalars().all()


@router.post("", response_model=PortionBoulangerieResponse, status_code=status.HTTP_201_CREATED)
async def create_portion(
    payload: PortionBoulangerieCreate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    portion = PortionPainBoulangerie(
        admin_boulangerie_id=admin_b.id,
        nom=payload.nom,
        equivalent_pains=payload.equivalent_pains,
        ordre=payload.ordre,
    )
    db.add(portion)
    await db.commit()
    await db.refresh(portion)
    return portion


@router.put("/{portion_id}", response_model=PortionBoulangerieResponse)
async def update_portion(
    portion_id: int,
    payload: PortionBoulangerieUpdate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    result = await db.execute(
        select(PortionPainBoulangerie).where(
            PortionPainBoulangerie.id == portion_id,
            PortionPainBoulangerie.admin_boulangerie_id == admin_b.id,
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


@router.delete("/{portion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portion(
    portion_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    result = await db.execute(
        select(PortionPainBoulangerie).where(
            PortionPainBoulangerie.id == portion_id,
            PortionPainBoulangerie.admin_boulangerie_id == admin_b.id,
        )
    )
    portion = result.scalar_one_or_none()
    if not portion:
        raise HTTPException(status_code=404, detail="Portion introuvable")

    await db.delete(portion)
    await db.commit()
