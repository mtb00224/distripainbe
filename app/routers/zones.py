from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_permission
from app.crud.zone import crud_zone
from app.db.session import get_db
from app.models.livreur import Livreur
from app.schemas.zone import ZoneCreate, ZoneResponse, ZoneUpdate

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("", response_model=list[ZoneResponse])
async def list_zones(
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_zones")),
):
    return await crud_zone.get_by_livreur(db, livreur.id)


@router.post("", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    payload: ZoneCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_zones")),
):
    return await crud_zone.create(db, obj_in={
        "livreur_id": livreur.id,
        "nom": payload.nom,
        "description": payload.description,
    })


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_zones")),
):
    z = await crud_zone.get_by_livreur_and_id(db, livreur.id, zone_id)
    if not z:
        raise HTTPException(status_code=404, detail="Zone introuvable")
    return z


@router.put("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: int,
    payload: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_zones")),
):
    z = await crud_zone.get_by_livreur_and_id(db, livreur.id, zone_id)
    if not z:
        raise HTTPException(status_code=404, detail="Zone introuvable")
    return await crud_zone.update(db, db_obj=z, obj_in=payload.model_dump(exclude_unset=True))


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_zones")),
):
    z = await crud_zone.get_by_livreur_and_id(db, livreur.id, zone_id)
    if not z:
        raise HTTPException(status_code=404, detail="Zone introuvable")
    await crud_zone.delete(db, id=zone_id)
