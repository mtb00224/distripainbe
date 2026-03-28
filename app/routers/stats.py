from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.models.livreur import Livreur
from app.schemas.stats import StatsPeriodeResponse, StatsClientResponse
from app.services import stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/journalier", response_model=StatsPeriodeResponse)
async def stats_journalier(
    date: date = Query(default_factory=date.today),
    boulangerie_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_stats")),
):
    return await stats_service.stats_journalier(db, livreur.id, date, boulangerie_id)


@router.get("/hebdomadaire", response_model=StatsPeriodeResponse)
async def stats_hebdomadaire(
    semaine: int = Query(default=1, ge=1, le=53),
    annee: int = Query(default_factory=lambda: date.today().year),
    boulangerie_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_stats")),
):
    return await stats_service.stats_hebdomadaire(db, livreur.id, semaine, annee, boulangerie_id)


@router.get("/mensuel", response_model=StatsPeriodeResponse)
async def stats_mensuel(
    mois: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
    annee: int = Query(default_factory=lambda: date.today().year),
    boulangerie_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_stats")),
):
    return await stats_service.stats_mensuel(db, livreur.id, mois, annee, boulangerie_id)


@router.get("/trimestriel", response_model=StatsPeriodeResponse)
async def stats_trimestriel(
    trimestre: int = Query(default=1, ge=1, le=4),
    annee: int = Query(default_factory=lambda: date.today().year),
    boulangerie_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_stats")),
):
    return await stats_service.stats_trimestriel(db, livreur.id, trimestre, annee, boulangerie_id)


@router.get("/semestriel", response_model=StatsPeriodeResponse)
async def stats_semestriel(
    semestre: int = Query(default=1, ge=1, le=2),
    annee: int = Query(default_factory=lambda: date.today().year),
    boulangerie_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_stats")),
):
    return await stats_service.stats_semestriel(db, livreur.id, semestre, annee, boulangerie_id)


@router.get("/annuel", response_model=StatsPeriodeResponse)
async def stats_annuel(
    annee: int = Query(default_factory=lambda: date.today().year),
    boulangerie_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_stats")),
):
    return await stats_service.stats_annuel(db, livreur.id, annee, boulangerie_id)


@router.get("/client/{client_id}", response_model=StatsClientResponse)
async def stats_client(
    client_id: int,
    date_debut: Optional[date] = Query(default=None),
    date_fin: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_stats")),
):
    return await stats_service.stats_client(db, livreur.id, client_id, date_debut, date_fin)
