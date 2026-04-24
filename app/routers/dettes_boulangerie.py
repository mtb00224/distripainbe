"""Dettes boulangerie — gestion des créances entre la boulangerie et ses livreurs internes.

GET    /admin-boulangerie/dettes              — liste des dettes (filtrable par type/statut)
POST   /admin-boulangerie/dettes              — créer une dette
PUT    /admin-boulangerie/dettes/{id}         — modifier motif / annuler
DELETE /admin-boulangerie/dettes/{id}         — supprimer
POST   /admin-boulangerie/dettes/{id}/reglements — ajouter un versement partiel/total
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.dette_boulangerie import (
    DetteBoulangerie,
    DetteBoulangerieStatut,
    DetteBoulangerieType,
    ReglementDetteBoulangerie,
)
from app.models.livreur_interne import LivreurInterne
from app.routers.admin_boulangerie import _require_active_boulangerie, AdminBoulangerie
from app.models.boulangerie import Boulangerie

router = APIRouter(prefix="/admin-boulangerie", tags=["dettes-boulangerie"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReglementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    montant: float
    notes: Optional[str] = None
    created_at: datetime


class DetteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    boulangerie_id: int
    livreur_interne_id: int
    livreur_prenom: str = ""
    livreur_nom: str = ""
    type: str
    motif: str
    montant_initial: float
    montant_restant: float
    statut: str
    created_at: datetime
    reglements: list[ReglementResponse] = []


class DetteCreate(BaseModel):
    livreur_interne_id: int
    type: DetteBoulangerieType
    motif: str
    montant: Decimal


class DetteUpdate(BaseModel):
    motif: Optional[str] = None
    statut: Optional[DetteBoulangerieStatut] = None


class ReglementCreate(BaseModel):
    montant: Decimal
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(d: DetteBoulangerie) -> DetteResponse:
    return DetteResponse(
        id=d.id,
        boulangerie_id=d.boulangerie_id,
        livreur_interne_id=d.livreur_interne_id,
        livreur_prenom=d.livreur_interne.prenom if d.livreur_interne else "",
        livreur_nom=d.livreur_interne.nom if d.livreur_interne else "",
        type=d.type.value,
        motif=d.motif,
        montant_initial=float(d.montant_initial),
        montant_restant=float(d.montant_restant),
        statut=d.statut.value,
        created_at=d.created_at,
        reglements=[
            ReglementResponse(
                id=r.id,
                montant=float(r.montant),
                notes=r.notes,
                created_at=r.created_at,
            )
            for r in d.reglements
        ],
    )


def _dette_query(boulangerie_id: int):
    return (
        select(DetteBoulangerie)
        .options(
            selectinload(DetteBoulangerie.livreur_interne),
            selectinload(DetteBoulangerie.reglements),
        )
        .where(DetteBoulangerie.boulangerie_id == boulangerie_id)
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/dettes", response_model=list[DetteResponse])
async def list_dettes(
    type: Optional[DetteBoulangerieType] = None,
    statut: Optional[DetteBoulangerieStatut] = None,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    stmt = _dette_query(boulangerie.id).order_by(DetteBoulangerie.created_at.desc())
    if type is not None:
        stmt = stmt.where(DetteBoulangerie.type == type)
    if statut is not None:
        stmt = stmt.where(DetteBoulangerie.statut == statut)
    result = await db.execute(stmt)
    return [_serialize(d) for d in result.scalars().all()]


@router.post("/dettes", response_model=DetteResponse, status_code=201)
async def create_dette(
    payload: DetteCreate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, boulangerie = context

    # Vérifier que le livreur appartient bien à cette boulangerie
    livreur = await db.get(LivreurInterne, payload.livreur_interne_id)
    if not livreur or livreur.boulangerie_id != boulangerie.id:
        raise HTTPException(status_code=404, detail="Livreur interne introuvable")

    dette = DetteBoulangerie(
        boulangerie_id=boulangerie.id,
        livreur_interne_id=payload.livreur_interne_id,
        type=payload.type,
        motif=payload.motif,
        montant_initial=payload.montant,
        montant_restant=payload.montant,
        statut=DetteBoulangerieStatut.EN_ATTENTE,
        created_by_id=admin_b.user_id,
    )
    db.add(dette)
    await db.commit()

    result = await db.execute(
        _dette_query(boulangerie.id).where(DetteBoulangerie.id == dette.id)
    )
    return _serialize(result.scalar_one())


@router.put("/dettes/{dette_id}", response_model=DetteResponse)
async def update_dette(
    dette_id: int,
    payload: DetteUpdate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    dette = await db.get(DetteBoulangerie, dette_id)
    if not dette or dette.boulangerie_id != boulangerie.id:
        raise HTTPException(status_code=404, detail="Dette introuvable")

    if payload.motif is not None:
        dette.motif = payload.motif
    if payload.statut is not None:
        dette.statut = payload.statut
        if payload.statut == DetteBoulangerieStatut.REGLE:
            dette.montant_restant = Decimal("0.00")
        elif payload.statut == DetteBoulangerieStatut.ANNULE:
            dette.montant_restant = Decimal("0.00")

    await db.commit()
    result = await db.execute(
        _dette_query(boulangerie.id).where(DetteBoulangerie.id == dette_id)
    )
    return _serialize(result.scalar_one())


@router.delete("/dettes/{dette_id}", status_code=204)
async def delete_dette(
    dette_id: int,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    dette = await db.get(DetteBoulangerie, dette_id)
    if not dette or dette.boulangerie_id != boulangerie.id:
        raise HTTPException(status_code=404, detail="Dette introuvable")
    await db.delete(dette)
    await db.commit()


@router.post("/dettes/{dette_id}/reglements", response_model=DetteResponse, status_code=201)
async def add_reglement(
    dette_id: int,
    payload: ReglementCreate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, boulangerie = context
    dette = await db.get(DetteBoulangerie, dette_id)
    if not dette or dette.boulangerie_id != boulangerie.id:
        raise HTTPException(status_code=404, detail="Dette introuvable")
    if dette.statut in (DetteBoulangerieStatut.REGLE, DetteBoulangerieStatut.ANNULE):
        raise HTTPException(status_code=400, detail="Cette dette est déjà soldée ou annulée")
    if payload.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")
    if payload.montant > dette.montant_restant:
        raise HTTPException(
            status_code=400,
            detail=f"Montant trop élevé (restant : {dette.montant_restant})",
        )

    reglement = ReglementDetteBoulangerie(
        dette_id=dette.id,
        montant=payload.montant,
        notes=payload.notes,
        created_by_id=admin_b.user_id,
    )
    db.add(reglement)

    dette.montant_restant -= payload.montant
    if dette.montant_restant <= Decimal("0.00"):
        dette.montant_restant = Decimal("0.00")
        dette.statut = DetteBoulangerieStatut.REGLE
    else:
        dette.statut = DetteBoulangerieStatut.PARTIELLEMENT_REGLE

    await db.commit()
    result = await db.execute(
        _dette_query(boulangerie.id).where(DetteBoulangerie.id == dette_id)
    )
    return _serialize(result.scalar_one())
