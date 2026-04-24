"""Dépenses boulangerie — sorties d'argent avec motif et catégorie.

GET  /admin-boulangerie/depenses/categories   — liste des catégories
POST /admin-boulangerie/depenses/categories   — créer une catégorie
GET  /admin-boulangerie/depenses              — liste dépenses (filtrable par date)
POST /admin-boulangerie/depenses              — enregistrer une dépense
DELETE /admin-boulangerie/depenses/{id}       — supprimer
"""

from datetime import date as DateType, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.boulangerie import Boulangerie, CategorieDepense, Depense
from app.routers.admin_boulangerie import _require_active_boulangerie, AdminBoulangerie

router = APIRouter(prefix="/admin-boulangerie", tags=["depenses-boulangerie"])


# ---------------------------------------------------------------------------
# Schemas inline
# ---------------------------------------------------------------------------

class CategorieDepenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    description: Optional[str] = None


class CategorieDepenseCreate(BaseModel):
    nom: str
    description: Optional[str] = None


class DepenseCreate(BaseModel):
    categorie_id: int
    motif: str
    quantite: Decimal = Decimal("1")
    prix_unitaire: Decimal
    date_enregistrement: Optional[datetime] = None


class DepenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    boulangerie_id: int
    categorie_id: int
    categorie_nom: str = ""
    motif: str
    quantite: float
    prix_unitaire: float
    montant_total: float
    date_enregistrement: datetime
    created_by_id: int


def _serialize(d: Depense) -> DepenseResponse:
    return DepenseResponse(
        id=d.id,
        boulangerie_id=d.boulangerie_id,
        categorie_id=d.categorie_id,
        categorie_nom=d.categorie.nom if d.categorie else "",
        motif=d.motif,
        quantite=float(d.quantite),
        prix_unitaire=float(d.prix_unitaire),
        montant_total=float(d.montant_total),
        date_enregistrement=d.date_enregistrement,
        created_by_id=d.created_by_id,
    )


# ---------------------------------------------------------------------------
# Catégories
# ---------------------------------------------------------------------------

@router.get("/depenses/categories", response_model=list[CategorieDepenseResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CategorieDepense).order_by(CategorieDepense.nom))
    return result.scalars().all()


@router.post("/depenses/categories", response_model=CategorieDepenseResponse, status_code=201)
async def create_categorie(
    payload: CategorieDepenseCreate,
    context=Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    cat = CategorieDepense(nom=payload.nom, description=payload.description)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# Dépenses
# ---------------------------------------------------------------------------

@router.get("/depenses", response_model=list[DepenseResponse])
async def list_depenses(
    date_debut: Optional[DateType] = None,
    date_fin: Optional[DateType] = None,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    stmt = (
        select(Depense)
        .options(selectinload(Depense.categorie))
        .where(Depense.boulangerie_id == boulangerie.id)
    )
    if date_debut:
        stmt = stmt.where(Depense.date_enregistrement >= datetime(date_debut.year, date_debut.month, date_debut.day))
    if date_fin:
        stmt = stmt.where(Depense.date_enregistrement <= datetime(date_fin.year, date_fin.month, date_fin.day, 23, 59, 59))
    stmt = stmt.order_by(Depense.date_enregistrement.desc())
    result = await db.execute(stmt)
    return [_serialize(d) for d in result.scalars().all()]


@router.post("/depenses", response_model=DepenseResponse, status_code=201)
async def create_depense(
    payload: DepenseCreate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, boulangerie = context

    cat = await db.get(CategorieDepense, payload.categorie_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Catégorie introuvable")

    depense = Depense(
        boulangerie_id=boulangerie.id,
        categorie_id=payload.categorie_id,
        motif=payload.motif,
        quantite=payload.quantite,
        prix_unitaire=payload.prix_unitaire,
        date_enregistrement=payload.date_enregistrement or datetime.now(timezone.utc),
        created_by_id=admin_b.user_id,
    )
    db.add(depense)
    await db.commit()

    result = await db.execute(
        select(Depense).options(selectinload(Depense.categorie)).where(Depense.id == depense.id)
    )
    return _serialize(result.scalar_one())


@router.delete("/depenses/{depense_id}", status_code=204)
async def delete_depense(
    depense_id: int,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    depense = await db.get(Depense, depense_id)
    if not depense or depense.boulangerie_id != boulangerie.id:
        raise HTTPException(status_code=404, detail="Dépense introuvable")
    await db.delete(depense)
    await db.commit()
