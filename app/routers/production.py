"""
Journal de production d'une boulangerie.

GET    /admin-boulangerie/production                     — Liste des sessions
POST   /admin-boulangerie/production                     — Créer une session
GET    /admin-boulangerie/production/{id}                — Détail d'une session
PUT    /admin-boulangerie/production/{id}                — Modifier (si OUVERTE)
POST   /admin-boulangerie/production/{id}/cloturer       — Clôturer
POST   /admin-boulangerie/production/{id}/distributions  — Ajouter distribution livreur
PUT    /admin-boulangerie/production/{id}/distributions/{dist_id}  — Saisir retours/encaissement
DELETE /admin-boulangerie/production/{id}/distributions/{dist_id}  — Supprimer distribution
"""
import math
from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.boulangerie import AdminBoulangerie, Boulangerie
from app.models.livreur_interne_portion import LivreurInternePortionPain
from app.models.livreur_interne import CompteInterneLivreur, LivreurInterne
from app.models.production import (
    DistributionLivreur,
    ModeReglement,
    RetourDistributionLigne,
    SessionProduction,
    StatutSession,
)
from app.routers.admin_boulangerie import _get_current_admin_boulangerie, _require_active_boulangerie
from app.schemas.production import (
    DistributionCreate,
    DistributionLivreurResponse,
    DistributionUpdate,
    RetourLigneBoulangerieIn,
    SessionProductionCreate,
    SessionProductionResponse,
    SessionProductionUpdate,
)

router = APIRouter(prefix="/admin-boulangerie/production", tags=["production"])


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

async def _load_session(
    session_id: int,
    admin_b: AdminBoulangerie,
    db: AsyncSession,
) -> SessionProduction:
    result = await db.execute(
        select(SessionProduction)
        .options(
            selectinload(SessionProduction.distributions).selectinload(
                DistributionLivreur.livreur_interne
            )
        )
        .join(Boulangerie, Boulangerie.id == SessionProduction.boulangerie_id)
        .where(
            SessionProduction.id == session_id,
            Boulangerie.admin_boulangerie_id == admin_b.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    return session


def _build_session_response(s: SessionProduction) -> SessionProductionResponse:
    return SessionProductionResponse(
        id=s.id,
        boulangerie_id=s.boulangerie_id,
        date=s.date,
        periode=s.periode,
        nb_pains_produits=s.nb_pains_produits,
        nb_pains_ambulatoire=s.nb_pains_ambulatoire,
        montant_ambulatoire=s.montant_ambulatoire,
        statut=s.statut,
        notes=s.notes,
        created_at=s.created_at,
        nb_pains_distribues=s.nb_pains_distribues,
        nb_pains_retournes_total=s.nb_pains_retournes_total,
        nb_pains_vendus_total=s.nb_pains_vendus_total,
        montant_encaisse_total=s.montant_encaisse_total,
        nb_pains_non_distribues=s.nb_pains_non_distribues,
        distributions=[
            DistributionLivreurResponse.from_orm_enriched(d) for d in s.distributions
        ],
    )


# ─────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────

@router.get("", response_model=list[SessionProductionResponse])
async def list_sessions(
    boulangerie_id: Optional[int] = None,
    date_debut: Optional[date_type] = None,
    date_fin: Optional[date_type] = None,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, boulangerie_active_id = context

    stmt = (
        select(SessionProduction)
        .options(
            selectinload(SessionProduction.distributions).selectinload(
                DistributionLivreur.livreur_interne
            )
        )
        .join(Boulangerie, Boulangerie.id == SessionProduction.boulangerie_id)
        .where(Boulangerie.admin_boulangerie_id == admin_b.id)
    )

    target_id = boulangerie_id or boulangerie_active_id
    if target_id:
        stmt = stmt.where(SessionProduction.boulangerie_id == target_id)
    if date_debut:
        stmt = stmt.where(SessionProduction.date >= date_debut)
    if date_fin:
        stmt = stmt.where(SessionProduction.date <= date_fin)

    result = await db.execute(stmt.order_by(SessionProduction.date.desc(), SessionProduction.periode))
    return [_build_session_response(s) for s in result.scalars().all()]


@router.post("", response_model=SessionProductionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionProductionCreate,
    context: tuple[AdminBoulangerie, Boulangerie] = Depends(_require_active_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, boulangerie = context

    # Vérifier qu'il n'existe pas déjà une session ouverte pour ce jour + période
    existing = await db.execute(
        select(SessionProduction).where(
            SessionProduction.boulangerie_id == boulangerie.id,
            SessionProduction.date == payload.date,
            SessionProduction.periode == payload.periode,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Une session {payload.periode} existe déjà pour le {payload.date}",
        )

    prix_vente = boulangerie.prix_vente_pain or Decimal("0")
    montant_ambulatoire = Decimal(payload.nb_pains_ambulatoire) * prix_vente

    session = SessionProduction(
        boulangerie_id=boulangerie.id,
        date=payload.date,
        periode=payload.periode,
        nb_pains_produits=payload.nb_pains_produits,
        nb_pains_ambulatoire=payload.nb_pains_ambulatoire,
        montant_ambulatoire=montant_ambulatoire,
        notes=payload.notes,
        created_by_id=admin_b.user_id,
    )
    db.add(session)
    await db.flush()
    await db.commit()

    # Recharger avec relations
    session = await _load_session(session.id, admin_b, db)
    return _build_session_response(session)


@router.get("/{session_id}", response_model=SessionProductionResponse)
async def get_session(
    session_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    session = await _load_session(session_id, admin_b, db)
    return _build_session_response(session)


@router.put("/{session_id}", response_model=SessionProductionResponse)
async def update_session(
    session_id: int,
    payload: SessionProductionUpdate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    session = await _load_session(session_id, admin_b, db)

    if session.statut == StatutSession.CLOTUREE:
        raise HTTPException(status_code=400, detail="Session déjà clôturée")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(session, field, value)

    # Recompute montant_ambulatoire if nb_pains_ambulatoire changed
    if "nb_pains_ambulatoire" in updates:
        boulangerie_result = await db.execute(
            select(Boulangerie).where(Boulangerie.id == session.boulangerie_id)
        )
        boulangerie = boulangerie_result.scalar_one_or_none()
        prix_vente = (boulangerie.prix_vente_pain if boulangerie else None) or Decimal("0")
        session.montant_ambulatoire = Decimal(session.nb_pains_ambulatoire) * prix_vente

    db.add(session)
    await db.commit()

    session = await _load_session(session_id, admin_b, db)
    return _build_session_response(session)


@router.post("/{session_id}/cloturer", response_model=SessionProductionResponse)
async def cloturer_session(
    session_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    session = await _load_session(session_id, admin_b, db)

    if session.statut == StatutSession.CLOTUREE:
        raise HTTPException(status_code=400, detail="Session déjà clôturée")

    session.statut = StatutSession.CLOTUREE
    db.add(session)
    await db.commit()

    session = await _load_session(session_id, admin_b, db)
    return _build_session_response(session)


# ─────────────────────────────────────────────
# Distributions
# ─────────────────────────────────────────────

@router.post("/{session_id}/distributions", response_model=DistributionLivreurResponse, status_code=201)
async def add_distribution(
    session_id: int,
    payload: DistributionCreate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    session = await _load_session(session_id, admin_b, db)

    if session.statut == StatutSession.CLOTUREE:
        raise HTTPException(status_code=400, detail="Session clôturée — impossible d'ajouter")

    # Vérifier que le livreur interne appartient à la même boulangerie
    li_result = await db.execute(
        select(LivreurInterne).where(
            LivreurInterne.id == payload.livreur_interne_id,
            LivreurInterne.boulangerie_id == session.boulangerie_id,
            LivreurInterne.is_active == True,
        )
    )
    li = li_result.scalar_one_or_none()
    if not li:
        raise HTTPException(status_code=404, detail="Livreur interne introuvable ou inactif")

    # Vérifier qu'il n'est pas déjà dans cette session
    existing = await db.execute(
        select(DistributionLivreur).where(
            DistributionLivreur.session_id == session_id,
            DistributionLivreur.livreur_interne_id == payload.livreur_interne_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ce livreur est déjà dans cette session")

    # Vérifier qu'on a assez de pains disponibles
    total_distribues = sum(d.nb_pains_donnes for d in session.distributions)
    disponibles = session.nb_pains_produits - session.nb_pains_ambulatoire - total_distribues
    if payload.nb_pains_donnes > disponibles:
        raise HTTPException(
            status_code=400,
            detail=f"Seulement {disponibles} pains disponibles (produits - ambulatoire - déjà distribués)",
        )

    # Prix : utiliser celui fourni ou le prix par défaut du livreur
    prix = payload.prix_par_pain if payload.prix_par_pain is not None else li.prix_achat_pain
    if not prix:
        raise HTTPException(
            status_code=400,
            detail="Prix par pain non renseigné — configurez-le sur le livreur ou fournissez-le manuellement",
        )

    dist = DistributionLivreur(
        session_id=session_id,
        livreur_interne_id=li.id,
        nb_pains_donnes=payload.nb_pains_donnes,
        prix_par_pain=prix,
    )
    db.add(dist)
    await db.commit()
    await db.refresh(dist)

    # Recharger avec relation livreur_interne
    result = await db.execute(
        select(DistributionLivreur)
        .options(selectinload(DistributionLivreur.livreur_interne))
        .where(DistributionLivreur.id == dist.id)
    )
    dist = result.scalar_one()
    return DistributionLivreurResponse.from_orm_enriched(dist)


@router.put("/{session_id}/distributions/{dist_id}", response_model=DistributionLivreurResponse)
async def update_distribution(
    session_id: int,
    dist_id: int,
    payload: DistributionUpdate,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    session = await _load_session(session_id, admin_b, db)

    dist_result = await db.execute(
        select(DistributionLivreur)
        .options(selectinload(DistributionLivreur.livreur_interne))
        .where(
            DistributionLivreur.id == dist_id,
            DistributionLivreur.session_id == session_id,
        )
    )
    dist = dist_result.scalar_one_or_none()
    if not dist:
        raise HTTPException(status_code=404, detail="Distribution introuvable")

    # Si lignes_retour fournies → calculer nb_pains_retournes depuis les portions
    lignes_retour = payload.lignes_retour
    if lignes_retour is not None:
        # Charger les portions concernées
        portion_ids = [l.portion_id for l in lignes_retour if l.quantite > 0]
        portions_map: dict[int, LivreurInternePortionPain] = {}
        if portion_ids:
            result_portions = await db.execute(
                select(LivreurInternePortionPain).where(
                    LivreurInternePortionPain.id.in_(portion_ids),
                    LivreurInternePortionPain.livreur_interne_id == dist.livreur_interne_id,
                )
            )
            for p in result_portions.scalars().all():
                portions_map[p.id] = p

        # Calculer total fractions de pains
        total_fractions = Decimal("0")
        for ligne in lignes_retour:
            if ligne.quantite <= 0 or ligne.portion_id not in portions_map:
                continue
            portion = portions_map[ligne.portion_id]
            total_fractions += Decimal(str(ligne.quantite)) * Decimal(str(portion.equivalent_pains))

        nb_pains_retournes_calc = math.floor(total_fractions)

        # Remplacer le détail retour
        await db.execute(
            sql_delete(RetourDistributionLigne).where(
                RetourDistributionLigne.distribution_id == dist_id
            )
        )
        for ligne in lignes_retour:
            if ligne.quantite > 0 and ligne.portion_id in portions_map:
                db.add(RetourDistributionLigne(
                    distribution_id=dist_id,
                    portion_id=ligne.portion_id,
                    quantite=ligne.quantite,
                ))

        dist.nb_pains_retournes = nb_pains_retournes_calc

    updates = payload.model_dump(exclude_unset=True, exclude={"lignes_retour"})
    for field, value in updates.items():
        setattr(dist, field, value)

    # Si mode_reglement = COMPTE_INTERNE → créditer le compte interne du livreur
    if payload.mode_reglement == ModeReglement.COMPTE_INTERNE and payload.montant_encaisse is not None:
        compte_result = await db.execute(
            select(CompteInterneLivreur).where(
                CompteInterneLivreur.livreur_interne_id == dist.livreur_interne_id
            )
        )
        compte = compte_result.scalar_one_or_none()
        if not compte:
            compte = CompteInterneLivreur(
                livreur_interne_id=dist.livreur_interne_id,
                solde_actuel=Decimal("0.00"),
            )
            db.add(compte)
            await db.flush()
        compte.solde_actuel += payload.montant_encaisse
        db.add(compte)

    db.add(dist)
    await db.commit()

    result = await db.execute(
        select(DistributionLivreur)
        .options(selectinload(DistributionLivreur.livreur_interne))
        .where(DistributionLivreur.id == dist_id)
    )
    dist = result.scalar_one()
    return DistributionLivreurResponse.from_orm_enriched(dist)


@router.delete("/{session_id}/distributions/{dist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_distribution(
    session_id: int,
    dist_id: int,
    context: tuple[AdminBoulangerie, Optional[int]] = Depends(_get_current_admin_boulangerie),
    db: AsyncSession = Depends(get_db),
):
    admin_b, _ = context
    session = await _load_session(session_id, admin_b, db)

    if session.statut == StatutSession.CLOTUREE:
        raise HTTPException(status_code=400, detail="Session clôturée — impossible de supprimer")

    dist_result = await db.execute(
        select(DistributionLivreur).where(
            DistributionLivreur.id == dist_id,
            DistributionLivreur.session_id == session_id,
        )
    )
    dist = dist_result.scalar_one_or_none()
    if not dist:
        raise HTTPException(status_code=404, detail="Distribution introuvable")

    await db.delete(dist)
    await db.commit()
