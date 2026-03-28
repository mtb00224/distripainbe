from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_livreur, require_permission
from app.crud.boulangerie import crud_boulangerie
from app.db.session import get_db
from app.models.livreur import Livreur
from app.schemas.boulangerie import BoulangerieCreate, BoulangerieResponse, BoulangerieUpdate

router = APIRouter(prefix="/boulangeries", tags=["boulangeries"])


@router.get("", response_model=list[BoulangerieResponse])
async def list_boulangeries(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_boulangeries")),
):
    return await crud_boulangerie.get_by_livreur(db, livreur.id, include_inactive=include_inactive)


@router.post("", response_model=BoulangerieResponse, status_code=status.HTTP_201_CREATED)
async def create_boulangerie(
    payload: BoulangerieCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_boulangeries")),
):
    return await crud_boulangerie.create(db, obj_in={
        "livreur_id": livreur.id,
        "nom": payload.nom,
        "contact": payload.contact,
        "prix_achat_pain": payload.prix_achat_pain,
        "is_default": False,
    })


@router.get("/{boulangerie_id}", response_model=BoulangerieResponse)
async def get_boulangerie(
    boulangerie_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_boulangeries")),
):
    b = await crud_boulangerie.get_by_livreur_and_id(db, livreur.id, boulangerie_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")
    return b


@router.put("/{boulangerie_id}", response_model=BoulangerieResponse)
async def update_boulangerie(
    boulangerie_id: int,
    payload: BoulangerieUpdate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_boulangeries")),
):
    b = await crud_boulangerie.get_by_livreur_and_id(db, livreur.id, boulangerie_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")
    updates = payload.model_dump(exclude_unset=True)
    return await crud_boulangerie.update(db, db_obj=b, obj_in=updates)


@router.delete("/{boulangerie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_boulangerie(
    boulangerie_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_boulangeries")),
):
    b = await crud_boulangerie.get_by_livreur_and_id(db, livreur.id, boulangerie_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")
    if b.is_default:
        raise HTTPException(status_code=400, detail="Impossible de supprimer la boulangerie par défaut")
    await crud_boulangerie.update(db, db_obj=b, obj_in={"is_active": False})
