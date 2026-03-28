"""
Debt management router.

Endpoints:
  GET    /dettes              — list debts (filter: client_id, statut)
  POST   /dettes              — create a debt manually
  GET    /dettes/{id}         — get one debt with reglements
  DELETE /dettes/{id}         — delete a debt (only if en_cours)
  POST   /dettes/{id}/solder  — fully settle
  POST   /dettes/{id}/solder-partiel — partially settle
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_acolyte_context, require_permission
from app.crud.client import crud_client
from app.crud.livraison_client import crud_livraison
from app.db.session import get_db
from app.models.client import Client as ClientModel
from app.models.dette import Dette, ReglementDette
from app.models.livreur import Livreur
from app.schemas.dette import DetteCreate, DetteResponse, ReglementCreate, ReglementResponse
from app.services.bilan_service import recalculate_client_solde

router = APIRouter(prefix="/dettes", tags=["dettes"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_response(dette: Dette, client_nom: str, zone_nom: str | None = None) -> DetteResponse:
    try:
        livraison_ids = json.loads(dette.livraison_ids or "[]")
    except (ValueError, TypeError):
        livraison_ids = []
    return DetteResponse(
        id=dette.id,
        livreur_id=dette.livreur_id,
        client_id=dette.client_id,
        client_nom=client_nom,
        zone_nom=zone_nom,
        encaissement_id=dette.encaissement_id,
        livraison_ids=livraison_ids,
        montant_initial=float(dette.montant_initial),
        montant_restant=float(dette.montant_restant),
        statut=dette.statut,
        notes=dette.notes,
        created_at=dette.created_at,
        reglements=[
            ReglementResponse(
                id=r.id,
                dette_id=r.dette_id,
                livreur_id=r.livreur_id,
                montant=float(r.montant),
                date_reglement=r.date_reglement,
                notes=r.notes,
                created_at=r.created_at,
            )
            for r in dette.reglements
        ],
    )


async def _get_dette_or_404(db: AsyncSession, dette_id: int, livreur_id: int) -> Dette:
    result = await db.execute(
        select(Dette)
        .options(selectinload(Dette.reglements))
        .where(Dette.id == dette_id, Dette.livreur_id == livreur_id)
    )
    dette = result.scalar_one_or_none()
    if not dette:
        raise HTTPException(status_code=404, detail="Dette introuvable")
    return dette


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DetteResponse])
async def list_dettes(
    client_id: Optional[int] = Query(default=None),
    statut: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_encaissements")),
):
    q = (
        select(Dette)
        .options(selectinload(Dette.reglements), selectinload(Dette.client).selectinload(ClientModel.zone))
        .where(Dette.livreur_id == livreur.id)
        .order_by(Dette.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if client_id:
        q = q.where(Dette.client_id == client_id)
    if statut:
        q = q.where(Dette.statut == statut)

    result = await db.execute(q)
    dettes = result.scalars().all()
    return [_build_response(d, d.client.nom if d.client else "", d.client.zone.nom if d.client and d.client.zone else None) for d in dettes]


# ---------------------------------------------------------------------------
# Create (manual)
# ---------------------------------------------------------------------------

@router.post("", response_model=DetteResponse, status_code=status.HTTP_201_CREATED)
async def create_dette(
    payload: DetteCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_encaissements")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, payload.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    dette = Dette(
        livreur_id=livreur.id,
        client_id=payload.client_id,
        livraison_ids=json.dumps(payload.livraison_ids),
        montant_initial=payload.montant_initial,
        montant_restant=payload.montant_initial,
        statut="en_cours",
        notes=payload.notes,
    )
    db.add(dette)
    await db.commit()
    await db.refresh(dette)

    result = await db.execute(
        select(Dette).options(selectinload(Dette.reglements), selectinload(Dette.client).selectinload(ClientModel.zone))
        .where(Dette.id == dette.id)
    )
    dette = result.scalar_one()
    return _build_response(dette, dette.client.nom if dette.client else "", dette.client.zone.nom if dette.client and dette.client.zone else None)


# ---------------------------------------------------------------------------
# Get one
# ---------------------------------------------------------------------------

@router.get("/{dette_id}", response_model=DetteResponse)
async def get_dette(
    dette_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_encaissements")),
):
    result = await db.execute(
        select(Dette)
        .options(selectinload(Dette.reglements), selectinload(Dette.client).selectinload(ClientModel.zone))
        .where(Dette.id == dette_id, Dette.livreur_id == livreur.id)
    )
    dette = result.scalar_one_or_none()
    if not dette:
        raise HTTPException(status_code=404, detail="Dette introuvable")
    return _build_response(dette, dette.client.nom if dette.client else "", dette.client.zone.nom if dette.client and dette.client.zone else None)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{dette_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dette(
    dette_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_encaissements")),
):
    dette = await _get_dette_or_404(db, dette_id, livreur.id)
    if dette.statut == "soldee_totalement":
        raise HTTPException(status_code=400, detail="Impossible de supprimer une dette totalement soldée")
    await db.delete(dette)
    await db.commit()


# ---------------------------------------------------------------------------
# Solder totalement
# ---------------------------------------------------------------------------

@router.post("/{dette_id}/solder", response_model=DetteResponse)
async def solder_dette(
    dette_id: int,
    payload: ReglementCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_encaissements")),
):
    dette = await _get_dette_or_404(db, dette_id, livreur.id)
    if dette.statut == "soldee_totalement":
        raise HTTPException(status_code=400, detail="Cette dette est déjà soldée")

    montant = Decimal(str(dette.montant_restant))
    reglement = ReglementDette(
        dette_id=dette.id,
        livreur_id=livreur.id,
        montant=montant,
        date_reglement=payload.date_reglement or datetime.now(timezone.utc),
        notes=payload.notes,
    )
    db.add(reglement)

    dette.montant_restant = Decimal("0")
    dette.statut = "soldee_totalement"
    db.add(dette)

    # Mark linked livraisons as paid
    try:
        livraison_ids = json.loads(dette.livraison_ids or "[]")
    except (ValueError, TypeError):
        livraison_ids = []
    if livraison_ids:
        await crud_livraison.mark_paid(db, livraison_ids, livreur.id)

    await db.commit()
    await recalculate_client_solde(db, dette.client_id)

    result = await db.execute(
        select(Dette).options(selectinload(Dette.reglements), selectinload(Dette.client).selectinload(ClientModel.zone))
        .where(Dette.id == dette.id)
    )
    dette = result.scalar_one()
    return _build_response(dette, dette.client.nom if dette.client else "", dette.client.zone.nom if dette.client and dette.client.zone else None)


# ---------------------------------------------------------------------------
# Solder partiellement
# ---------------------------------------------------------------------------

@router.post("/{dette_id}/solder-partiel", response_model=DetteResponse)
async def solder_dette_partiel(
    dette_id: int,
    payload: ReglementCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_encaissements")),
):
    dette = await _get_dette_or_404(db, dette_id, livreur.id)
    if dette.statut == "soldee_totalement":
        raise HTTPException(status_code=400, detail="Cette dette est déjà soldée")

    montant = Decimal(str(payload.montant))
    if montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")
    if montant > dette.montant_restant:
        raise HTTPException(
            status_code=400,
            detail=f"Montant ({montant}) supérieur au restant ({dette.montant_restant})"
        )

    reglement = ReglementDette(
        dette_id=dette.id,
        livreur_id=livreur.id,
        montant=montant,
        date_reglement=payload.date_reglement or datetime.now(timezone.utc),
        notes=payload.notes,
    )
    db.add(reglement)

    dette.montant_restant = dette.montant_restant - montant
    if dette.montant_restant == 0:
        dette.statut = "soldee_totalement"
        # Mark livraisons paid
        try:
            livraison_ids = json.loads(dette.livraison_ids or "[]")
        except (ValueError, TypeError):
            livraison_ids = []
        if livraison_ids:
            await crud_livraison.mark_paid(db, livraison_ids, livreur.id)
    else:
        dette.statut = "soldee_partiellement"
    db.add(dette)

    await db.commit()
    await recalculate_client_solde(db, dette.client_id)

    result = await db.execute(
        select(Dette).options(selectinload(Dette.reglements), selectinload(Dette.client).selectinload(ClientModel.zone))
        .where(Dette.id == dette.id)
    )
    dette = result.scalar_one()
    return _build_response(dette, dette.client.nom if dette.client else "", dette.client.zone.nom if dette.client and dette.client.zone else None)
