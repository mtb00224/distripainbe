"""Subscription management — livreur-facing endpoints.

GET  /abonnements/formules              — active formulas
GET  /abonnements/moyens-paiement       — active payment methods (filtered by livreur's pays)
GET  /abonnements/current               — livreur's current/latest subscription
POST /abonnements                       — subscribe to a formula
POST /abonnements/{id}/paiement         — declare a payment
GET  /abonnements/history               — all past subscriptions
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import livreur_only
from app.db.session import get_db
from app.models.abonnement import Abonnement, FormulaAbonnement, PaiementAbonnement
from app.models.livreur import Livreur
from app.models.moyen_paiement import MoyenPaiement
from app.models.pays import Pays
from app.schemas.abonnement import (
    AbonnementCreate,
    AbonnementResponse,
    FormulaAbonnementResponse,
    PaiementAbonnementCreate,
    PaiementAbonnementResponse,
)
from app.schemas.moyen_paiement import MoyenPaiementResponse

router = APIRouter(prefix="/abonnements", tags=["abonnements"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_paiement(p: PaiementAbonnement, livreur_nom: str) -> PaiementAbonnementResponse:
    return PaiementAbonnementResponse(
        id=p.id,
        abonnement_id=p.abonnement_id,
        livreur_id=p.livreur_id,
        livreur_nom=livreur_nom,
        montant=float(p.montant),
        moyen=p.moyen,
        reference=p.reference,
        statut=p.statut,
        notes_admin=p.notes_admin,
        date_paiement=p.date_paiement,
        date_validation=p.date_validation,
        created_at=p.created_at,
    )


def _build_abonnement(a: Abonnement, livreur_nom: str) -> AbonnementResponse:
    formule = FormulaAbonnementResponse(
        id=a.formule.id,
        nom=a.formule.nom,
        duree_mois=a.formule.duree_mois,
        prix=float(a.formule.prix),
        description=a.formule.description,
        is_active=a.formule.is_active,
        created_at=a.formule.created_at,
    )
    return AbonnementResponse(
        id=a.id,
        livreur_id=a.livreur_id,
        livreur_nom=livreur_nom,
        formule_id=a.formule_id,
        formule=formule,
        date_debut=a.date_debut,
        date_fin=a.date_fin,
        statut=a.statut,
        created_at=a.created_at,
        paiements=[_build_paiement(p, livreur_nom) for p in a.paiements],
    )


# ---------------------------------------------------------------------------
# Formulas (public within livreur context)
# ---------------------------------------------------------------------------

@router.get("/formules", response_model=list[FormulaAbonnementResponse])
async def list_formules(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    """Returns active formulas matching the livreur's pays, plus global formulas (pays_id=null)."""
    from sqlalchemy import or_
    result = await db.execute(
        select(FormulaAbonnement)
        .options(selectinload(FormulaAbonnement.pays))
        .where(
            FormulaAbonnement.is_active == True,
            or_(
                FormulaAbonnement.pays_id == None,
                FormulaAbonnement.pays_id == livreur.pays_id,
            ),
        )
        .order_by(FormulaAbonnement.duree_mois)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Pays (active countries — used by client form)
# ---------------------------------------------------------------------------

@router.get("/pays", response_model=list)
async def list_pays_actifs(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.pays import PaysResponse
    result = await db.execute(
        select(Pays).where(Pays.is_active == True).order_by(Pays.nom)
    )
    pays_list = result.scalars().all()
    return [PaysResponse.model_validate(p) for p in pays_list]


# ---------------------------------------------------------------------------
# Payment methods
# ---------------------------------------------------------------------------

@router.get("/moyens-paiement", response_model=list[MoyenPaiementResponse])
async def list_moyens_paiement(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    """Returns active payment methods filtered by livreur's pays (+ global methods with pays_id=null).
    If the livreur has no pays assigned, returns all active methods."""
    from sqlalchemy import or_
    conditions = [MoyenPaiement.is_active == True]
    if livreur.pays_id is not None:
        conditions.append(
            or_(MoyenPaiement.pays_id == None, MoyenPaiement.pays_id == livreur.pays_id)
        )
    result = await db.execute(
        select(MoyenPaiement)
        .options(selectinload(MoyenPaiement.pays))
        .where(*conditions)
        .order_by(MoyenPaiement.pays_id.nullslast(), MoyenPaiement.nom)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Current subscription
# ---------------------------------------------------------------------------

@router.get("/current", response_model=Optional[AbonnementResponse])
async def get_current_abonnement(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Abonnement)
        .options(
            selectinload(Abonnement.formule),
            selectinload(Abonnement.paiements),
        )
        .where(Abonnement.livreur_id == livreur.id)
        .order_by(Abonnement.created_at.desc())
        .limit(1)
    )
    abonnement = result.scalar_one_or_none()
    if not abonnement:
        return None
    return _build_abonnement(abonnement, livreur.nom)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.get("/history", response_model=list[AbonnementResponse])
async def get_abonnement_history(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Abonnement)
        .options(
            selectinload(Abonnement.formule),
            selectinload(Abonnement.paiements),
        )
        .where(Abonnement.livreur_id == livreur.id)
        .order_by(Abonnement.created_at.desc())
    )
    abonnements = result.scalars().all()
    return [_build_abonnement(a, livreur.nom) for a in abonnements]


# ---------------------------------------------------------------------------
# Subscribe
# ---------------------------------------------------------------------------

@router.post("", response_model=AbonnementResponse, status_code=status.HTTP_201_CREATED)
async def create_abonnement(
    payload: AbonnementCreate,
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    formule = await db.get(FormulaAbonnement, payload.formule_id)
    if not formule or not formule.is_active:
        raise HTTPException(status_code=404, detail="Formule introuvable ou inactive")

    date_fin = payload.date_debut + timedelta(days=formule.duree_mois * 30)

    abonnement = Abonnement(
        livreur_id=livreur.id,
        formule_id=formule.id,
        date_debut=payload.date_debut,
        date_fin=date_fin,
        statut="en_attente",
    )
    db.add(abonnement)
    await db.commit()
    await db.refresh(abonnement)

    result = await db.execute(
        select(Abonnement)
        .options(selectinload(Abonnement.formule), selectinload(Abonnement.paiements))
        .where(Abonnement.id == abonnement.id)
    )
    abonnement = result.scalar_one()
    return _build_abonnement(abonnement, livreur.nom)


# ---------------------------------------------------------------------------
# Declare a payment
# ---------------------------------------------------------------------------

@router.post("/{abonnement_id}/paiement",
             response_model=PaiementAbonnementResponse,
             status_code=status.HTTP_201_CREATED)
async def declare_paiement(
    abonnement_id: int,
    payload: PaiementAbonnementCreate,
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Abonnement).where(
            Abonnement.id == abonnement_id,
            Abonnement.livreur_id == livreur.id,
        )
    )
    abonnement = result.scalar_one_or_none()
    if not abonnement:
        raise HTTPException(status_code=404, detail="Abonnement introuvable")
    if abonnement.statut == "expire":
        raise HTTPException(status_code=400, detail="Abonnement expiré")

    paiement = PaiementAbonnement(
        abonnement_id=abonnement_id,
        livreur_id=livreur.id,
        montant=payload.montant,
        moyen=payload.moyen,
        reference=payload.reference,
        statut="en_attente",
    )
    db.add(paiement)
    await db.commit()
    await db.refresh(paiement)
    return _build_paiement(paiement, livreur.nom)
