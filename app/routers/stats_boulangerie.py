"""Statistiques boulangerie — résumé sur une période.

GET /admin-boulangerie/stats                — stats boulangerie active
GET /admin-boulangerie/stats/global         — stats de toutes les boulangeries de l'admin
"""

from datetime import date as DateType, datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.boulangerie import Boulangerie, Depense
from app.models.production import SessionProduction, DistributionLivreur, StatutSession
from app.routers.admin_boulangerie import (
    _require_active_boulangerie, _get_current_admin_boulangerie, AdminBoulangerie
)

router = APIRouter(prefix="/admin-boulangerie", tags=["stats-boulangerie"])


class StatsBoulangerieResponse(BaseModel):
    boulangerie_id: Optional[int] = None
    boulangerie_nom: Optional[str] = None
    date_debut: Optional[str] = None
    date_fin: Optional[str] = None
    # Sessions
    nb_sessions_total: int = 0
    nb_sessions_cloturees: int = 0
    # Production
    nb_pains_produits: int = 0
    nb_pains_ambulatoire: int = 0
    nb_pains_distribues: int = 0
    nb_pains_vendus: int = 0
    # Finances
    montant_ambulatoire: float = 0.0
    montant_encaisse: float = 0.0
    total_depenses: float = 0.0
    benefice_net: float = 0.0


@router.get("/stats", response_model=StatsBoulangerieResponse)
async def get_stats(
    date_debut: Optional[DateType] = None,
    date_fin: Optional[DateType] = None,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    _, boulangerie = context
    return await _compute_stats_for_boulangerie(db, boulangerie, date_debut, date_fin)


async def _compute_stats_for_boulangerie(
    db: AsyncSession,
    boulangerie: Boulangerie,
    date_debut: Optional[DateType],
    date_fin: Optional[DateType],
) -> StatsBoulangerieResponse:
    """Calcule les stats pour une boulangerie donnée (logique partagée)."""
    sess_stmt = select(SessionProduction).where(SessionProduction.boulangerie_id == boulangerie.id)
    if date_debut:
        sess_stmt = sess_stmt.where(SessionProduction.date >= date_debut)
    if date_fin:
        sess_stmt = sess_stmt.where(SessionProduction.date <= date_fin)
    sessions_result = await db.execute(sess_stmt)
    sessions = sessions_result.scalars().all()

    nb_sessions_total = len(sessions)
    nb_sessions_cloturees = sum(1 for s in sessions if s.statut == StatutSession.CLOTUREE)
    nb_pains_produits = sum(s.nb_pains_produits for s in sessions)
    nb_pains_ambulatoire = sum(s.nb_pains_ambulatoire or 0 for s in sessions)
    montant_ambulatoire = float(sum(s.montant_ambulatoire or 0 for s in sessions))

    session_ids = [s.id for s in sessions]
    montant_encaisse = 0.0
    nb_pains_distribues = 0
    nb_pains_vendus = 0

    if session_ids:
        dist_result = await db.execute(
            select(DistributionLivreur).where(DistributionLivreur.session_id.in_(session_ids))
        )
        distributions = dist_result.scalars().all()
        nb_pains_distribues = sum(d.nb_pains_donnes for d in distributions)
        nb_pains_vendus = sum(d.nb_pains_donnes - (d.nb_pains_retournes or 0) for d in distributions)
        montant_encaisse = float(sum(d.montant_encaisse or 0 for d in distributions)) + montant_ambulatoire

    dep_stmt = select(Depense).where(Depense.boulangerie_id == boulangerie.id)
    if date_debut:
        dep_stmt = dep_stmt.where(
            Depense.date_enregistrement >= datetime(date_debut.year, date_debut.month, date_debut.day)
        )
    if date_fin:
        dep_stmt = dep_stmt.where(
            Depense.date_enregistrement <= datetime(date_fin.year, date_fin.month, date_fin.day, 23, 59, 59)
        )
    dep_result = await db.execute(dep_stmt)
    total_depenses = float(sum(d.quantite * d.prix_unitaire for d in dep_result.scalars().all()))

    return StatsBoulangerieResponse(
        boulangerie_id=boulangerie.id,
        boulangerie_nom=boulangerie.nom,
        date_debut=str(date_debut) if date_debut else None,
        date_fin=str(date_fin) if date_fin else None,
        nb_sessions_total=nb_sessions_total,
        nb_sessions_cloturees=nb_sessions_cloturees,
        nb_pains_produits=nb_pains_produits,
        nb_pains_ambulatoire=nb_pains_ambulatoire,
        nb_pains_distribues=nb_pains_distribues,
        nb_pains_vendus=nb_pains_vendus,
        montant_ambulatoire=montant_ambulatoire,
        montant_encaisse=montant_encaisse,
        total_depenses=total_depenses,
        benefice_net=montant_encaisse - total_depenses,
    )


class GlobalStatsResponse(BaseModel):
    date_debut: Optional[str] = None
    date_fin: Optional[str] = None
    boulangeries: list[StatsBoulangerieResponse] = []
    total: StatsBoulangerieResponse = StatsBoulangerieResponse()


@router.get("/stats/global", response_model=GlobalStatsResponse)
async def get_stats_global(
    date_debut: Optional[DateType] = None,
    date_fin: Optional[DateType] = None,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    """Stats agrégées pour toutes les boulangeries de l'admin connecté."""
    admin_b, _ = context

    result = await db.execute(
        select(Boulangerie)
        .where(Boulangerie.admin_boulangerie_id == admin_b.id, Boulangerie.is_active == True)
        .order_by(Boulangerie.nom)
    )
    boulangeries = result.scalars().all()

    stats_list: list[StatsBoulangerieResponse] = []
    for b in boulangeries:
        s = await _compute_stats_for_boulangerie(db, b, date_debut, date_fin)
        stats_list.append(s)

    # Totaux agrégés
    total = StatsBoulangerieResponse(
        boulangerie_id=None,
        boulangerie_nom="Total",
        date_debut=str(date_debut) if date_debut else None,
        date_fin=str(date_fin) if date_fin else None,
        nb_sessions_total=sum(s.nb_sessions_total for s in stats_list),
        nb_sessions_cloturees=sum(s.nb_sessions_cloturees for s in stats_list),
        nb_pains_produits=sum(s.nb_pains_produits for s in stats_list),
        nb_pains_ambulatoire=sum(s.nb_pains_ambulatoire for s in stats_list),
        nb_pains_distribues=sum(s.nb_pains_distribues for s in stats_list),
        nb_pains_vendus=sum(s.nb_pains_vendus for s in stats_list),
        montant_ambulatoire=sum(s.montant_ambulatoire for s in stats_list),
        montant_encaisse=sum(s.montant_encaisse for s in stats_list),
        total_depenses=sum(s.total_depenses for s in stats_list),
        benefice_net=sum(s.benefice_net for s in stats_list),
    )

    return GlobalStatsResponse(
        date_debut=str(date_debut) if date_debut else None,
        date_fin=str(date_fin) if date_fin else None,
        boulangeries=stats_list,
        total=total,
    )
