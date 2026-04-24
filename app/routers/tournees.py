from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_acolyte_context, require_permission
from app.crud.client import crud_client
from app.crud.encaissement import crud_encaissement
from app.crud.livraison_client import crud_livraison
from app.crud.portion_pain import crud_portion
from app.crud.tournee import crud_tournee
from app.db.session import get_db
from app.models.livreur import Livreur
from app.models.livraison_client import LivraisonClient
from app.models.retour_pain import RetourPain as RetourBoulangerieLigne
from app.schemas.livraison_client import BulkLivraisonsCreate, LivraisonClientResponse, LivraisonClientUpdate
from app.schemas.tournee import TourneeCreate, TourneeResponse, TourneeUpdate
from app.services.bilan_service import recalculate_client_solde


class TerminerClientRequest(BaseModel):
    notes: Optional[str] = None
    encaisser: bool = False
    montant: Optional[Decimal] = None
    type_encaissement: Optional[str] = None  # 'complet', 'partiel', 'dette'


class RetourLigneIn(BaseModel):
    portion_pain_id: int
    quantite: int = 0


class RetourBoulangerieRequest(BaseModel):
    lignes: list[RetourLigneIn]


router = APIRouter(prefix="/tournees", tags=["tournees"])


@router.get("", response_model=list[TourneeResponse])
async def list_tournees(
    date_filter: Optional[date] = Query(default=None, alias="date"),
    periode: Optional[str] = Query(default=None),
    boulangerie_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_tournees")),
):
    return await crud_tournee.get_by_livreur(
        db, livreur.id,
        date_filter=date_filter,
        periode=periode,
        boulangerie_id=boulangerie_id,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=TourneeResponse, status_code=status.HTTP_201_CREATED)
async def create_tournee(
    payload: TourneeCreate,
    context=Depends(get_current_acolyte_context),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("create_tournees")),
):
    _, acolyte = context
    t = await crud_tournee.create(db, obj_in={
        "livreur_id": livreur.id,
        "boulangerie_id": payload.boulangerie_id,
        "date": payload.date,
        "periode": payload.periode,
        "nb_pains_pris": payload.nb_pains_pris,
        "nb_pains_ecoules": 0,
        "nb_pains_retournes": 0,
        "notes": payload.notes,
        "created_by_id": acolyte.user_id if acolyte else livreur.user_id,
    })
    return await crud_tournee.get_by_livreur_and_id(db, livreur.id, t.id)


@router.get("/{tournee_id}", response_model=TourneeResponse)
async def get_tournee(
    tournee_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_tournees")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")
    return t


@router.put("/{tournee_id}", response_model=TourneeResponse)
async def update_tournee(
    tournee_id: int,
    payload: TourneeUpdate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("update_tournees")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")
    updates = payload.model_dump(exclude_unset=True)
    # Recalculate nb_pains_retournes if relevant fields changed
    pris = updates.get("nb_pains_pris", t.nb_pains_pris)
    ecoules = updates.get("nb_pains_ecoules", t.nb_pains_ecoules)
    updates["nb_pains_retournes"] = max(0, pris - ecoules)
    await crud_tournee.update(db, db_obj=t, obj_in=updates)
    return await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)


@router.patch("/{tournee_id}/terminer", response_model=TourneeResponse)
async def terminer_tournee(
    tournee_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("terminer_tournees")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")
    if t.statut == "terminee":
        raise HTTPException(status_code=400, detail="Tournée déjà terminée")

    updates: dict = {"statut": "terminee"}

    # Auto-calculate from client livraisons if livreur didn't set the figures manually
    if t.nb_pains_ecoules == 0:
        livraisons = await crud_livraison.get_by_tournee(db, tournee_id)
        auto_ecoules = sum(max(0, l.nb_pains_livres - l.nb_pains_retournes) for l in livraisons)
        updates["nb_pains_ecoules"] = auto_ecoules
        updates["nb_pains_retournes"] = max(0, t.nb_pains_pris - auto_ecoules)

    await crud_tournee.update(db, db_obj=t, obj_in=updates)
    return await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)


@router.patch("/{tournee_id}/clients/{client_id}/terminer", response_model=TourneeResponse)
async def terminer_client(
    tournee_id: int,
    client_id: int,
    payload: TerminerClientRequest,
    context=Depends(get_current_acolyte_context),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("terminer_tournees")),
):
    """Terminer les livraisons d'un client dans une tournée, avec option d'encaissement."""
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")
    if t.statut == "terminee":
        raise HTTPException(status_code=400, detail="Tournée déjà terminée")

    # Fetch all livraisons for this client in this tournee
    all_livraisons = await crud_livraison.get_by_tournee(db, tournee_id)
    client_livraisons = [lv for lv in all_livraisons if lv.client_id == client_id]
    if not client_livraisons:
        raise HTTPException(status_code=404, detail="Aucune livraison pour ce client dans cette tournée")

    # Mark all client livraisons as terminated
    for lv in client_livraisons:
        lv.is_termine = True
        db.add(lv)
    await db.commit()

    # Optionally create encaissement
    if payload.encaisser and payload.montant is not None and payload.type_encaissement:
        _, acolyte = context
        livraison_ids = [lv.id for lv in client_livraisons]
        enc = await crud_encaissement.create_encaissement(
            db,
            livreur_id=livreur.id,
            client_id=client_id,
            montant=payload.montant if payload.type_encaissement != "dette" else Decimal("0"),
            livraisons_soldees=livraison_ids,
            type_enc=payload.type_encaissement,
            notes=payload.notes,
            date_encaissement=datetime.now(timezone.utc),
            acolyte_id=acolyte.id if acolyte else None,
        )
        if payload.type_encaissement == "complet":
            await crud_livraison.mark_paid(db, livraison_ids, livreur.id)
        await recalculate_client_solde(db, client_id)

    # Check if all clients are terminated → auto-close tournée
    refreshed_livraisons = await crud_livraison.get_by_tournee(db, tournee_id)
    if all(lv.is_termine for lv in refreshed_livraisons) and refreshed_livraisons:
        updates: dict = {"statut": "terminee"}
        if t.nb_pains_ecoules == 0:
            auto_ecoules = sum(max(0, lv.nb_pains_livres - lv.nb_pains_retournes) for lv in refreshed_livraisons)
            updates["nb_pains_ecoules"] = auto_ecoules
            updates["nb_pains_retournes"] = max(0, t.nb_pains_pris - auto_ecoules)
        await crud_tournee.update(db, db_obj=t, obj_in=updates)

    return await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)


@router.get("/{tournee_id}/livraisons", response_model=list[LivraisonClientResponse])
async def get_livraisons(
    tournee_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_tournees")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")
    return await crud_livraison.get_by_tournee(db, tournee_id)


@router.post("/{tournee_id}/livraisons", response_model=list[LivraisonClientResponse], status_code=status.HTTP_201_CREATED)
async def set_livraisons(
    tournee_id: int,
    payload: BulkLivraisonsCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_livraisons")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")

    # Validate: existing + new net deliveries must not exceed pains pris
    existing = await crud_livraison.get_by_tournee(db, tournee_id)
    existing_net = sum(max(0, l.nb_pains_livres - l.nb_pains_retournes) for l in existing)
    new_net = sum(max(0, item.nb_pains_livres - item.nb_pains_retournes) for item in payload.livraisons)
    if existing_net + new_net > t.nb_pains_pris:
        raise HTTPException(
            status_code=400,
            detail=f"Total livraisons nettes ({existing_net + new_net}) dépasse les pains pris ({t.nb_pains_pris})"
        )

    affected_clients = set()

    for item in payload.livraisons:
        client = await crud_client.get_by_livreur_and_id(db, livreur.id, item.client_id)
        if not client:
            raise HTTPException(status_code=404, detail=f"Client {item.client_id} introuvable")

        prix = client.prix_vente_pain or Decimal("0")
        net_pains = max(0, item.nb_pains_livres - item.nb_pains_retournes)
        montant = prix * net_pains

        livraison = LivraisonClient(
            tournee_id=tournee_id,
            client_id=item.client_id,
            livreur_id=livreur.id,
            nb_pains_livres=item.nb_pains_livres,
            nb_pains_retournes=item.nb_pains_retournes,
            prix_unitaire=prix,
            montant_du=montant,
            created_by_id=livreur.user_id,
        )
        db.add(livraison)
        affected_clients.add(item.client_id)

    await db.commit()

    for client_id in affected_clients:
        await recalculate_client_solde(db, client_id)

    return await crud_livraison.get_by_tournee(db, tournee_id)


@router.put("/{tournee_id}/livraisons/{livraison_id}", response_model=LivraisonClientResponse)
async def update_livraison(
    tournee_id: int,
    livraison_id: int,
    payload: LivraisonClientUpdate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_livraisons")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")

    lv = await crud_livraison.get_by_livreur_and_id(db, livreur.id, livraison_id)
    if not lv or lv.tournee_id != tournee_id:
        raise HTTPException(status_code=404, detail="Livraison introuvable")

    nb_livres = payload.nb_pains_livres if payload.nb_pains_livres is not None else lv.nb_pains_livres
    nb_retournes = payload.nb_pains_retournes if payload.nb_pains_retournes is not None else lv.nb_pains_retournes

    # Validate: other livraisons + updated net must not exceed pains pris
    all_livraisons = await crud_livraison.get_by_tournee(db, tournee_id)
    other_net = sum(max(0, l.nb_pains_livres - l.nb_pains_retournes) for l in all_livraisons if l.id != livraison_id)
    new_net = max(0, nb_livres - nb_retournes)
    if other_net + new_net > t.nb_pains_pris:
        raise HTTPException(
            status_code=400,
            detail=f"Total livraisons nettes ({other_net + new_net}) dépasserait les pains pris ({t.nb_pains_pris})"
        )

    montant = lv.prix_unitaire * new_net
    await crud_livraison.update(db, db_obj=lv, obj_in={
        "nb_pains_livres": nb_livres,
        "nb_pains_retournes": nb_retournes,
        "montant_du": montant,
    })
    await recalculate_client_solde(db, lv.client_id)

    refreshed = await crud_livraison.get_by_tournee(db, tournee_id)
    return next(l for l in refreshed if l.id == livraison_id)


@router.delete("/{tournee_id}/livraisons/{livraison_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_livraison(
    tournee_id: int,
    livraison_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_livraisons")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")

    lv = await crud_livraison.get_by_livreur_and_id(db, livreur.id, livraison_id)
    if not lv or lv.tournee_id != tournee_id:
        raise HTTPException(status_code=404, detail="Livraison introuvable")

    client_id = lv.client_id
    await crud_livraison.delete(db, id=livraison_id)
    await recalculate_client_solde(db, client_id)


# ── Retour boulangerie par portion ──────────────────────────────────────────

async def _build_retour_response(db: AsyncSession, livreur_id: int, tournee_id: int, t):
    portions = await crud_portion.get_by_livreur(db, livreur_id)
    result = await db.execute(
        select(RetourBoulangerieLigne).where(RetourBoulangerieLigne.tournee_id == tournee_id)
    )
    existing = {r.portion_pain_id: r.quantite for r in result.scalars().all()}
    lignes = []
    valeur_retour = 0
    for p in portions:
        qty = existing.get(p.id, 0)
        valeur_retour += qty * p.prix_fcfa
        lignes.append({
            "portion_pain_id": p.id,
            "portion_nom": p.nom,
            "prix_fcfa": p.prix_fcfa,
            "quantite": qty,
        })
    return {"nb_retournes": t.nb_pains_retournes, "valeur_retour": valeur_retour, "lignes": lignes, "tournee": t}


@router.get("/{tournee_id}/retour-boulangerie")
async def get_retour_boulangerie(
    tournee_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_tournees")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")
    return await _build_retour_response(db, livreur.id, tournee_id, t)


@router.post("/{tournee_id}/retour-boulangerie")
async def save_retour_boulangerie(
    tournee_id: int,
    payload: RetourBoulangerieRequest,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("update_tournees")),
):
    t = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tournée introuvable")
    if t.statut == "terminee":
        raise HTTPException(status_code=400, detail="Tournée déjà terminée")

    portions = await crud_portion.get_by_livreur(db, livreur.id)
    portions_map = {p.id: p for p in portions}

    # Replace existing breakdown
    await db.execute(sql_delete(RetourBoulangerieLigne).where(RetourBoulangerieLigne.tournee_id == tournee_id))

    total_retournes = 0
    for ligne in payload.lignes:
        if ligne.quantite <= 0 or ligne.portion_pain_id not in portions_map:
            continue
        db.add(RetourBoulangerieLigne(tournee_id=tournee_id, portion_pain_id=ligne.portion_pain_id, quantite=ligne.quantite))
        total_retournes += ligne.quantite

    nb_ecoules = max(0, t.nb_pains_pris - total_retournes)
    await crud_tournee.update(db, db_obj=t, obj_in={"nb_pains_retournes": total_retournes, "nb_pains_ecoules": nb_ecoules})
    await db.commit()

    refreshed = await crud_tournee.get_by_livreur_and_id(db, livreur.id, tournee_id)
    return await _build_retour_response(db, livreur.id, tournee_id, refreshed)
