"""Gestion des abonnements — endpoints livreur.

GET  /abonnements/formules         — Formules actives
GET  /abonnements/moyens-paiement  — Moyens de paiement disponibles
GET  /abonnements/current          — Abonnement actuel du livreur
GET  /abonnements/history          — Historique des abonnements
POST /abonnements                  — S'abonner à une formule
POST /abonnements/{id}/paiement    — Déclarer un paiement
"""

from datetime import date, timedelta, timezone, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional

from app.core.dependencies import livreur_only
from app.db.session import get_db
from app.models.abonnement import Abonnement, FormulaAbonnement, MoyenPaiement, PaiementAbonnement
from app.models.livreur import Livreur
from app.schemas.abonnement import (
    AbonnementCreate,
    AbonnementResponse,
    FormulaAbonnementResponse,
    PaiementAbonnementCreate,
    PaiementAbonnementResponse,
)
from app.schemas.moyen_paiement import MoyenPaiementResponse

router = APIRouter(prefix="/abonnements", tags=["abonnements"])


def _build_paiement(p: PaiementAbonnement) -> PaiementAbonnementResponse:
    return PaiementAbonnementResponse(
        id=p.id,
        abonnement_id=p.abonnement_id,
        montant=p.montant,
        reference=p.reference,
        statut=p.statut,
        date_paiement=p.date_paiement,
        valide_par_id=p.valide_par_id,
    )


def _build_abonnement(a: Abonnement) -> AbonnementResponse:
    formule = FormulaAbonnementResponse(
        id=a.formule.id,
        nom=a.formule.nom,
        cible=a.formule.cible,
        duree_mois=a.formule.duree_mois,
        prix=float(a.formule.prix),
        max_boulangeries=a.formule.max_boulangeries,
        description=a.formule.description,
        is_active=a.formule.is_active,
        created_at=a.formule.created_at,
    )
    return AbonnementResponse(
        id=a.id,
        livreur_id=a.livreur_id,
        boulangerie_id=a.boulangerie_id,
        formule_id=a.formule_id,
        formule=formule,
        date_debut=a.date_debut,
        date_fin=a.date_fin,
        statut=a.statut,
        created_at=a.created_at,
        paiements=[_build_paiement(p) for p in a.paiements],
    )


@router.get("/formules", response_model=list[FormulaAbonnementResponse])
async def list_formules(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FormulaAbonnement)
        .where(FormulaAbonnement.is_active == True)
        .order_by(FormulaAbonnement.duree_mois)
    )
    formules = result.scalars().all()
    return [
        FormulaAbonnementResponse(
            id=f.id,
            nom=f.nom,
            cible=f.cible,
            duree_mois=f.duree_mois,
            prix=float(f.prix),
            max_boulangeries=f.max_boulangeries,
            description=f.description,
            is_active=f.is_active,
            created_at=f.created_at,
        )
        for f in formules
    ]


@router.get("/moyens-paiement", response_model=list[MoyenPaiementResponse])
async def list_moyens_paiement(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MoyenPaiement).where(MoyenPaiement.is_active == True).order_by(MoyenPaiement.nom)
    )
    return result.scalars().all()


@router.get("/current", response_model=Optional[AbonnementResponse])
async def get_current_abonnement(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Abonnement)
        .options(selectinload(Abonnement.formule), selectinload(Abonnement.paiements))
        .where(Abonnement.livreur_id == livreur.id)
        .order_by(Abonnement.created_at.desc())
        .limit(1)
    )
    abonnement = result.scalar_one_or_none()
    return _build_abonnement(abonnement) if abonnement else None


@router.get("/history", response_model=list[AbonnementResponse])
async def get_abonnement_history(
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Abonnement)
        .options(selectinload(Abonnement.formule), selectinload(Abonnement.paiements))
        .where(Abonnement.livreur_id == livreur.id)
        .order_by(Abonnement.created_at.desc())
    )
    return [_build_abonnement(a) for a in result.scalars().all()]


@router.post("", response_model=AbonnementResponse, status_code=status.HTTP_201_CREATED)
async def create_abonnement(
    payload: AbonnementCreate,
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    formule = await db.get(FormulaAbonnement, payload.formule_id)
    if not formule or not formule.is_active:
        raise HTTPException(status_code=404, detail="Formule introuvable ou inactive")

    date_debut = payload.date_debut or date.today()
    date_fin = date_debut + timedelta(days=formule.duree_mois * 30)

    abonnement = Abonnement(
        livreur_id=livreur.id,
        formule_id=formule.id,
        date_debut=date_debut,
        date_fin=date_fin,
        statut="en_attente",
    )
    db.add(abonnement)
    await db.commit()

    result = await db.execute(
        select(Abonnement)
        .options(selectinload(Abonnement.formule), selectinload(Abonnement.paiements))
        .where(Abonnement.id == abonnement.id)
    )
    return _build_abonnement(result.scalar_one())


@router.post(
    "/{abonnement_id}/paiement",
    response_model=PaiementAbonnementResponse,
    status_code=status.HTTP_201_CREATED,
)
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
    if abonnement.statut.value == "expire":
        raise HTTPException(status_code=400, detail="Abonnement expiré")

    paiement = PaiementAbonnement(
        abonnement_id=abonnement_id,
        montant=payload.montant,
        reference=payload.reference,
        statut="en_attente",
    )
    db.add(paiement)
    await db.commit()
    await db.refresh(paiement)
    return _build_paiement(paiement)
