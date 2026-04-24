"""Catalogue des produits de vente ambulatoire.

GET    /admin-boulangerie/vente-ambulatoire          — Liste les produits
POST   /admin-boulangerie/vente-ambulatoire          — Créer un produit
PUT    /admin-boulangerie/vente-ambulatoire/{id}     — Modifier un produit
DELETE /admin-boulangerie/vente-ambulatoire/{id}     — Supprimer un produit
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.boulangerie import Boulangerie
from app.models.vente_ambulatoire import ProduitAmbulateur
from app.routers.admin_boulangerie import (
    _require_active_boulangerie, AdminBoulangerie
)

router = APIRouter(prefix="/admin-boulangerie", tags=["vente-ambulatoire"])


class ProduitAmbulateurResponse(BaseModel):
    id: int
    boulangerie_id: int
    nom: str
    description: Optional[str] = None
    unite: Optional[str] = None
    prix_unitaire: float
    is_active: bool

    model_config = {"from_attributes": True}


class ProduitAmbulateurCreate(BaseModel):
    nom: str
    description: Optional[str] = None
    unite: Optional[str] = None
    prix_unitaire: float


class ProduitAmbulateurUpdate(BaseModel):
    nom: Optional[str] = None
    description: Optional[str] = None
    unite: Optional[str] = None
    prix_unitaire: Optional[float] = None
    is_active: Optional[bool] = None


@router.get("/vente-ambulatoire", response_model=list[ProduitAmbulateurResponse])
async def list_produits(
    include_inactive: bool = False,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    stmt = select(ProduitAmbulateur).where(ProduitAmbulateur.boulangerie_id == boulangerie.id)
    if not include_inactive:
        stmt = stmt.where(ProduitAmbulateur.is_active == True)
    stmt = stmt.order_by(ProduitAmbulateur.nom)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/vente-ambulatoire", response_model=ProduitAmbulateurResponse, status_code=201)
async def create_produit(
    payload: ProduitAmbulateurCreate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    produit = ProduitAmbulateur(
        boulangerie_id=boulangerie.id,
        nom=payload.nom,
        description=payload.description,
        unite=payload.unite,
        prix_unitaire=payload.prix_unitaire,
    )
    db.add(produit)
    await db.commit()
    await db.refresh(produit)
    return produit


@router.put("/vente-ambulatoire/{produit_id}", response_model=ProduitAmbulateurResponse)
async def update_produit(
    produit_id: int,
    payload: ProduitAmbulateurUpdate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    produit = await db.get(ProduitAmbulateur, produit_id)
    if not produit or produit.boulangerie_id != boulangerie.id:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(produit, field, value)
    await db.commit()
    await db.refresh(produit)
    return produit


@router.delete("/vente-ambulatoire/{produit_id}", status_code=204)
async def delete_produit(
    produit_id: int,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    produit = await db.get(ProduitAmbulateur, produit_id)
    if not produit or produit.boulangerie_id != boulangerie.id:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    await db.delete(produit)
    await db.commit()
