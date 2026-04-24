from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_permission
from app.crud.portion_pain import crud_portion
from app.db.session import get_db
from app.models.livreur import Livreur
from app.schemas.portion_pain import PortionPainCreate, PortionPainResponse, PortionPainUpdate

router = APIRouter(prefix="/portions", tags=["portions"])


@router.get("", response_model=list[PortionPainResponse])
async def list_portions(
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_boulangeries")),
):
    await crud_portion.ensure_defaults(db, livreur.id)
    return await crud_portion.get_by_livreur(db, livreur.id)


@router.post("", response_model=PortionPainResponse, status_code=status.HTTP_201_CREATED)
async def create_portion(
    payload: PortionPainCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_boulangeries")),
):
    portion = await crud_portion.create(db, obj_in={
        "livreur_id": livreur.id,
        "nom": payload.nom,
        "prix_fcfa": payload.prix_fcfa,
        "valeur_unitaire": payload.valeur_unitaire,
    })
    return portion


@router.put("/{portion_id}", response_model=PortionPainResponse)
async def update_portion(
    portion_id: int,
    payload: PortionPainUpdate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_boulangeries")),
):
    p = await crud_portion.get_by_livreur_and_id(db, livreur.id, portion_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portion introuvable")
    updates = payload.model_dump(exclude_unset=True)
    return await crud_portion.update(db, db_obj=p, obj_in=updates)


@router.delete("/{portion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portion(
    portion_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_boulangeries")),
):
    p = await crud_portion.get_by_livreur_and_id(db, livreur.id, portion_id)
    if not p:
        raise HTTPException(status_code=404, detail="Portion introuvable")
    await crud_portion.delete(db, id=portion_id)
