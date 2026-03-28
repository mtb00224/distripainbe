"""
Stats service — aggregates data for all reporting periods.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tournee import Tournee
from app.models.livraison_client import LivraisonClient
from app.models.encaissement import Encaissement
from app.models.client import Client
from app.schemas.stats import StatsPeriodeResponse, StatsClientResponse


def _payment_status(solde: Decimal) -> str:
    if solde <= 0:
        return "solde"
    return "impaye"


async def _aggregate_tournees(
    db: AsyncSession,
    livreur_id: int,
    date_debut: date,
    date_fin: date,
    boulangerie_id: Optional[int] = None,
) -> dict:
    stmt = select(
        func.count(Tournee.id).label("nb_tournees"),
        func.coalesce(func.sum(Tournee.nb_pains_pris), 0).label("total_pains_pris"),
        func.coalesce(func.sum(Tournee.nb_pains_ecoules), 0).label("total_pains_ecoules"),
        func.coalesce(func.sum(Tournee.nb_pains_retournes), 0).label("total_pains_retournes"),
    ).where(
        Tournee.livreur_id == livreur_id,
        Tournee.date >= date_debut,
        Tournee.date <= date_fin,
        Tournee.statut != "annulee",
    )
    if boulangerie_id:
        stmt = stmt.where(Tournee.boulangerie_id == boulangerie_id)
    result = await db.execute(stmt)
    row = result.one()
    return {
        "nb_tournees": row.nb_tournees or 0,
        "total_pains_pris": row.total_pains_pris or 0,
        "total_pains_ecoules": row.total_pains_ecoules or 0,
        "total_pains_retournes": row.total_pains_retournes or 0,
    }


async def _aggregate_livraisons(
    db: AsyncSession,
    livreur_id: int,
    date_debut: date,
    date_fin: date,
    boulangerie_id: Optional[int] = None,
) -> Decimal:
    stmt = select(
        func.coalesce(func.sum(LivraisonClient.montant_du), 0).label("total_montant_du")
    ).join(
        Tournee, LivraisonClient.tournee_id == Tournee.id
    ).where(
        LivraisonClient.livreur_id == livreur_id,
        Tournee.date >= date_debut,
        Tournee.date <= date_fin,
    )
    if boulangerie_id:
        stmt = stmt.where(Tournee.boulangerie_id == boulangerie_id)
    result = await db.execute(stmt)
    return Decimal(str(result.scalar_one() or 0))


async def _aggregate_encaissements(
    db: AsyncSession,
    livreur_id: int,
    date_debut: date,
    date_fin: date,
) -> Decimal:
    stmt = select(
        func.coalesce(func.sum(Encaissement.montant), 0).label("total_encaisse")
    ).where(
        Encaissement.livreur_id == livreur_id,
        func.date(Encaissement.date_encaissement) >= date_debut,
        func.date(Encaissement.date_encaissement) <= date_fin,
    )
    result = await db.execute(stmt)
    return Decimal(str(result.scalar_one() or 0))


def _build_response(
    periode: str,
    tournee_data: dict,
    total_montant_du: Decimal,
    total_encaisse: Decimal,
    boulangerie_id: Optional[int],
) -> StatsPeriodeResponse:
    pris = tournee_data["total_pains_pris"]
    ecoules = tournee_data["total_pains_ecoules"]
    taux = round((ecoules / pris * 100) if pris > 0 else 0.0, 2)
    return StatsPeriodeResponse(
        periode=periode,
        total_pains_pris=pris,
        total_pains_ecoules=ecoules,
        total_pains_retournes=tournee_data["total_pains_retournes"],
        total_montant_du=total_montant_du,
        total_encaisse=total_encaisse,
        taux_ecoulement=taux,
        boulangerie_id=boulangerie_id,
        nb_tournees=tournee_data["nb_tournees"],
    )


async def stats_journalier(
    db: AsyncSession,
    livreur_id: int,
    jour: date,
    boulangerie_id: Optional[int] = None,
) -> StatsPeriodeResponse:
    tournee_data = await _aggregate_tournees(db, livreur_id, jour, jour, boulangerie_id)
    total_du = await _aggregate_livraisons(db, livreur_id, jour, jour, boulangerie_id)
    total_enc = await _aggregate_encaissements(db, livreur_id, jour, jour)
    return _build_response(str(jour), tournee_data, total_du, total_enc, boulangerie_id)


async def stats_hebdomadaire(
    db: AsyncSession,
    livreur_id: int,
    semaine: int,
    annee: int,
    boulangerie_id: Optional[int] = None,
) -> StatsPeriodeResponse:
    jan4 = date(annee, 1, 4)
    monday = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=semaine - 1)
    sunday = monday + timedelta(days=6)
    tournee_data = await _aggregate_tournees(db, livreur_id, monday, sunday, boulangerie_id)
    total_du = await _aggregate_livraisons(db, livreur_id, monday, sunday, boulangerie_id)
    total_enc = await _aggregate_encaissements(db, livreur_id, monday, sunday)
    return _build_response(f"S{semaine}-{annee}", tournee_data, total_du, total_enc, boulangerie_id)


async def stats_mensuel(
    db: AsyncSession,
    livreur_id: int,
    mois: int,
    annee: int,
    boulangerie_id: Optional[int] = None,
) -> StatsPeriodeResponse:
    debut = date(annee, mois, 1)
    if mois == 12:
        fin = date(annee + 1, 1, 1) - timedelta(days=1)
    else:
        fin = date(annee, mois + 1, 1) - timedelta(days=1)
    tournee_data = await _aggregate_tournees(db, livreur_id, debut, fin, boulangerie_id)
    total_du = await _aggregate_livraisons(db, livreur_id, debut, fin, boulangerie_id)
    total_enc = await _aggregate_encaissements(db, livreur_id, debut, fin)
    mois_names = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
    return _build_response(f"{mois_names[mois-1]} {annee}", tournee_data, total_du, total_enc, boulangerie_id)


async def stats_trimestriel(
    db: AsyncSession,
    livreur_id: int,
    trimestre: int,
    annee: int,
    boulangerie_id: Optional[int] = None,
) -> StatsPeriodeResponse:
    mois_debut = (trimestre - 1) * 3 + 1
    debut = date(annee, mois_debut, 1)
    mois_fin = mois_debut + 2
    if mois_fin == 12:
        fin = date(annee + 1, 1, 1) - timedelta(days=1)
    else:
        fin = date(annee, mois_fin + 1, 1) - timedelta(days=1)
    tournee_data = await _aggregate_tournees(db, livreur_id, debut, fin, boulangerie_id)
    total_du = await _aggregate_livraisons(db, livreur_id, debut, fin, boulangerie_id)
    total_enc = await _aggregate_encaissements(db, livreur_id, debut, fin)
    return _build_response(f"T{trimestre} {annee}", tournee_data, total_du, total_enc, boulangerie_id)


async def stats_semestriel(
    db: AsyncSession,
    livreur_id: int,
    semestre: int,
    annee: int,
    boulangerie_id: Optional[int] = None,
) -> StatsPeriodeResponse:
    debut = date(annee, 1, 1) if semestre == 1 else date(annee, 7, 1)
    fin = date(annee, 6, 30) if semestre == 1 else date(annee, 12, 31)
    tournee_data = await _aggregate_tournees(db, livreur_id, debut, fin, boulangerie_id)
    total_du = await _aggregate_livraisons(db, livreur_id, debut, fin, boulangerie_id)
    total_enc = await _aggregate_encaissements(db, livreur_id, debut, fin)
    return _build_response(f"S{semestre} {annee}", tournee_data, total_du, total_enc, boulangerie_id)


async def stats_annuel(
    db: AsyncSession,
    livreur_id: int,
    annee: int,
    boulangerie_id: Optional[int] = None,
) -> StatsPeriodeResponse:
    debut = date(annee, 1, 1)
    fin = date(annee, 12, 31)
    tournee_data = await _aggregate_tournees(db, livreur_id, debut, fin, boulangerie_id)
    total_du = await _aggregate_livraisons(db, livreur_id, debut, fin, boulangerie_id)
    total_enc = await _aggregate_encaissements(db, livreur_id, debut, fin)
    return _build_response(str(annee), tournee_data, total_du, total_enc, boulangerie_id)


async def stats_client(
    db: AsyncSession,
    livreur_id: int,
    client_id: int,
    date_debut: Optional[date] = None,
    date_fin: Optional[date] = None,
) -> StatsClientResponse:
    client_result = await db.execute(
        select(Client).where(Client.id == client_id, Client.livreur_id == livreur_id)
    )
    client = client_result.scalar_one_or_none()
    if not client:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Client introuvable")

    stmt = select(
        func.count(LivraisonClient.id).label("nb"),
        func.coalesce(func.sum(LivraisonClient.nb_pains_livres), 0).label("total_pains"),
        func.coalesce(func.sum(LivraisonClient.montant_du), 0).label("total_du"),
    ).where(
        LivraisonClient.client_id == client_id,
        LivraisonClient.livreur_id == livreur_id,
    )
    if date_debut:
        stmt = stmt.join(Tournee, LivraisonClient.tournee_id == Tournee.id).where(
            Tournee.date >= date_debut
        )
    if date_fin:
        if date_debut:
            stmt = stmt.where(Tournee.date <= date_fin)
        else:
            stmt = stmt.join(Tournee, LivraisonClient.tournee_id == Tournee.id).where(
                Tournee.date <= date_fin
            )
    livraison_data = (await db.execute(stmt)).one()

    enc_stmt = select(
        func.coalesce(func.sum(Encaissement.montant), 0).label("total_enc")
    ).where(
        Encaissement.client_id == client_id,
        Encaissement.livreur_id == livreur_id,
    )
    enc_data = (await db.execute(enc_stmt)).one()

    total_du = Decimal(str(livraison_data.total_du))
    total_enc = Decimal(str(enc_data.total_enc))
    solde = total_du - total_enc

    return StatsClientResponse(
        client_id=client_id,
        client_nom=client.nom,
        total_livraisons=livraison_data.nb or 0,
        total_pains_livres=livraison_data.total_pains or 0,
        montant_total_du=total_du,
        montant_encaisse=total_enc,
        solde=solde,
        statut=_payment_status(solde),
    )
