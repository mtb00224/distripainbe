"""
Portions de pain par client (côté livreur indépendant).

GET    /clients/{id}/portions
POST   /clients/{id}/portions
PUT    /clients/{id}/portions/{portion_id}
DELETE /clients/{id}/portions/{portion_id}
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_permission
from app.crud.client import crud_client
from app.db.session import get_db
from app.models.client_portion import ClientPortionPain
from app.models.livreur import Livreur

router = APIRouter(prefix="/clients", tags=["client-portions"])


# ── Schemas inline ────────────────────────────────────────────────────────────

class ClientPortionCreate(BaseModel):
    nom: str
    prix_fcfa: Decimal
    valeur_unitaire: Decimal = Decimal("1.0")


class ClientPortionUpdate(BaseModel):
    nom: Optional[str] = None
    prix_fcfa: Optional[Decimal] = None
    valeur_unitaire: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ClientPortionResponse(BaseModel):
    id: int
    client_id: int
    livreur_id: int
    nom: str
    prix_fcfa: Decimal
    valeur_unitaire: Decimal
    is_active: bool

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{client_id}/portions", response_model=list[ClientPortionResponse])
async def list_portions(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    result = await db.execute(
        select(ClientPortionPain)
        .where(
            ClientPortionPain.client_id == client_id,
            ClientPortionPain.livreur_id == livreur.id,
        )
        .order_by(ClientPortionPain.nom)
    )
    return result.scalars().all()


@router.post("/{client_id}/portions", response_model=ClientPortionResponse, status_code=status.HTTP_201_CREATED)
async def create_portion(
    client_id: int,
    payload: ClientPortionCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    portion = ClientPortionPain(
        client_id=client_id,
        livreur_id=livreur.id,
        nom=payload.nom,
        prix_fcfa=payload.prix_fcfa,
        valeur_unitaire=payload.valeur_unitaire,
    )
    db.add(portion)
    await db.commit()
    await db.refresh(portion)
    return portion


@router.put("/{client_id}/portions/{portion_id}", response_model=ClientPortionResponse)
async def update_portion(
    client_id: int,
    portion_id: int,
    payload: ClientPortionUpdate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    result = await db.execute(
        select(ClientPortionPain).where(
            ClientPortionPain.id == portion_id,
            ClientPortionPain.client_id == client_id,
            ClientPortionPain.livreur_id == livreur.id,
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


@router.delete("/{client_id}/portions/{portion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portion(
    client_id: int,
    portion_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    result = await db.execute(
        select(ClientPortionPain).where(
            ClientPortionPain.id == portion_id,
            ClientPortionPain.client_id == client_id,
            ClientPortionPain.livreur_id == livreur.id,
        )
    )
    portion = result.scalar_one_or_none()
    if not portion:
        raise HTTPException(status_code=404, detail="Portion introuvable")
    await db.delete(portion)
    await db.commit()
