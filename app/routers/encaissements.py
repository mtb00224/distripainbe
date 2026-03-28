import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_acolyte_context, require_permission
from app.crud.client import crud_client
from app.crud.encaissement import crud_encaissement
from app.crud.livraison_client import crud_livraison
from app.db.session import get_db
from app.models.dette import Dette, ReglementDette
from app.models.livreur import Livreur
from app.schemas.encaissement import (
    EncaissementCreate, EncaissementResponse, PendingLivraisonResponse,
    PendingTourneeResponse, ClientWithPendingResponse,
)
from app.services.bilan_service import recalculate_client_solde

router = APIRouter(prefix="/encaissements", tags=["encaissements"])


def _serialize(enc, /) -> EncaissementResponse:
    """Deserialize JSON fields before building the response."""
    try:
        livraisons_ids = json.loads(enc.livraisons_soldees or "[]")
    except (ValueError, TypeError):
        livraisons_ids = []
    data = {
        "id": enc.id,
        "livreur_id": enc.livreur_id,
        "client_id": enc.client_id,
        "montant": enc.montant,
        "date_encaissement": enc.date_encaissement,
        "livraisons_soldees": livraisons_ids,
        "type": enc.type,
        "notes": enc.notes,
        "created_at": enc.created_at,
        "client": enc.client,
    }
    return EncaissementResponse(**data)


@router.get("", response_model=list[EncaissementResponse])
async def list_encaissements(
    client_id: Optional[int] = Query(default=None),
    date_debut: Optional[datetime] = Query(default=None),
    date_fin: Optional[datetime] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_encaissements")),
):
    encs = await crud_encaissement.get_by_livreur(
        db, livreur.id, client_id=client_id,
        date_debut=date_debut, date_fin=date_fin, skip=skip, limit=limit,
    )
    return [_serialize(e) for e in encs]


@router.post("", response_model=EncaissementResponse, status_code=status.HTTP_201_CREATED)
async def create_encaissement(
    payload: EncaissementCreate,
    context=Depends(get_current_acolyte_context),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_encaissements")),
):
    _, acolyte = context

    client = await crud_client.get_by_livreur_and_id(db, livreur.id, payload.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    enc = await crud_encaissement.create_encaissement(
        db,
        livreur_id=livreur.id,
        client_id=payload.client_id,
        montant=payload.montant,
        livraisons_soldees=payload.livraisons_soldees,
        type_enc=payload.type,
        notes=payload.notes,
        date_encaissement=payload.date_encaissement,
        acolyte_id=acolyte.id if acolyte else None,
    )

    livraison_ids_set = set(payload.livraisons_soldees or [])

    if payload.type == "complet" and livraison_ids_set:
        # Mark livraisons paid
        await crud_livraison.mark_paid(db, list(livraison_ids_set), livreur.id)
        # Settle any active dettes linked to these livraisons
        r = await db.execute(
            select(Dette).where(
                Dette.livreur_id == livreur.id,
                Dette.client_id == payload.client_id,
                Dette.statut != "soldee_totalement",
            )
        )
        for dette in r.scalars().all():
            try:
                dette_lv_ids = set(json.loads(dette.livraison_ids or "[]"))
            except (ValueError, TypeError):
                dette_lv_ids = set()
            if dette_lv_ids & livraison_ids_set:
                db.add(ReglementDette(
                    dette_id=dette.id,
                    livreur_id=livreur.id,
                    montant=dette.montant_restant,
                    date_reglement=datetime.now(timezone.utc),
                    notes="Soldée via encaissement",
                ))
                dette.montant_restant = Decimal("0")
                dette.statut = "soldee_totalement"
                db.add(dette)
        await db.commit()

    elif payload.type == "partiel" and livraison_ids_set:
        livraisons = await crud_livraison.get_by_ids(db, list(livraison_ids_set), livreur.id)
        total_livraisons = sum(Decimal(str(lv.montant_du)) for lv in livraisons)
        # Find existing active dette for these livraisons
        r = await db.execute(
            select(Dette).where(
                Dette.livreur_id == livreur.id,
                Dette.client_id == payload.client_id,
                Dette.statut != "soldee_totalement",
            )
        )
        existing_dette = None
        for d in r.scalars().all():
            try:
                d_ids = set(json.loads(d.livraison_ids or "[]"))
            except (ValueError, TypeError):
                d_ids = set()
            if d_ids & livraison_ids_set:
                existing_dette = d
                break

        montant_paye = Decimal(str(payload.montant))
        if existing_dette:
            new_restant = existing_dette.montant_restant - montant_paye
            if new_restant <= 0:
                # Fully cleared via partial payment — mark everything done
                db.add(ReglementDette(
                    dette_id=existing_dette.id,
                    livreur_id=livreur.id,
                    montant=existing_dette.montant_restant,
                    date_reglement=datetime.now(timezone.utc),
                    notes="Soldée via paiement",
                ))
                existing_dette.montant_restant = Decimal("0")
                existing_dette.statut = "soldee_totalement"
                db.add(existing_dette)
                await crud_livraison.mark_paid(db, list(livraison_ids_set), livreur.id)
            else:
                db.add(ReglementDette(
                    dette_id=existing_dette.id,
                    livreur_id=livreur.id,
                    montant=montant_paye,
                    date_reglement=datetime.now(timezone.utc),
                    notes=None,
                ))
                existing_dette.montant_restant = new_restant
                existing_dette.statut = "soldee_partiellement"
                db.add(existing_dette)
            await db.commit()
        else:
            restant = total_livraisons - montant_paye
            if restant > 0:
                db.add(Dette(
                    livreur_id=livreur.id,
                    client_id=payload.client_id,
                    encaissement_id=enc.id,
                    livraison_ids=json.dumps(list(livraison_ids_set)),
                    montant_initial=restant,
                    montant_restant=restant,
                    statut="en_cours",
                    notes=f"Reste après paiement partiel de {payload.montant} XOF",
                ))
                await db.commit()

    elif payload.type == "dette" and livraison_ids_set:
        livraisons = await crud_livraison.get_by_ids(db, list(livraison_ids_set), livreur.id)
        montant_dette = sum(Decimal(str(lv.montant_du)) for lv in livraisons)
        if montant_dette > 0:
            db.add(Dette(
                livreur_id=livreur.id,
                client_id=payload.client_id,
                encaissement_id=enc.id,
                livraison_ids=json.dumps(list(livraison_ids_set)),
                montant_initial=montant_dette,
                montant_restant=montant_dette,
                statut="en_cours",
                notes=payload.notes,
            ))
            await db.commit()

    await recalculate_client_solde(db, payload.client_id)

    enc_with_client = await crud_encaissement.get_by_livreur_and_id(db, livreur.id, enc.id)
    return _serialize(enc_with_client)


@router.get("/clients-with-pending", response_model=list[ClientWithPendingResponse])
async def get_clients_with_pending(
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_encaissements")),
):
    """Returns only clients who have at least one unpaid (is_paid=False) livraison."""
    from app.models.livraison_client import LivraisonClient
    from app.models.tournee import Tournee
    from app.models.client import Client
    from sqlalchemy import distinct, func as sqlfunc

    from app.models.zone import Zone
    from sqlalchemy.orm import selectinload

    # Clients with unpaid livraisons
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.zone))
        .join(LivraisonClient, LivraisonClient.client_id == Client.id)
        .join(Tournee, LivraisonClient.tournee_id == Tournee.id)
        .where(
            LivraisonClient.livreur_id == livreur.id,
            LivraisonClient.is_paid == False,
            Tournee.statut == "terminee",
        )
        .distinct()
        .order_by(Client.nom)
    )
    clients = result.scalars().all()

    out = []
    for c in clients:
        r2 = await db.execute(
            select(
                sqlfunc.count(distinct(LivraisonClient.tournee_id)),
                sqlfunc.sum(LivraisonClient.montant_du),
            ).join(Tournee, LivraisonClient.tournee_id == Tournee.id)
            .where(
                LivraisonClient.client_id == c.id,
                LivraisonClient.livreur_id == livreur.id,
                LivraisonClient.is_paid == False,
                Tournee.statut == "terminee",
            )
        )
        row = r2.one()
        out.append(ClientWithPendingResponse(
            client_id=c.id,
            client_nom=c.nom,
            zone_nom=c.zone.nom if c.zone else None,
            telephone=c.telephone,
            solde_actuel=float(c.solde_actuel or 0),
            nb_tournees_pending=row[0] or 0,
            montant_total_pending=float(row[1] or 0),
        ))
    return out


@router.get("/pending-tournees", response_model=list[PendingTourneeResponse])
async def get_pending_tournees(
    client_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_encaissements")),
):
    """Returns unpaid livraisons grouped by tournée for a specific client, with debt info."""
    livraisons = await crud_livraison.get_unpaid_by_client(db, livreur.id, client_id=client_id)

    # Group by tournée
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for lv in livraisons:
        groups[lv.tournee_id].append(lv)

    # Fetch active dettes for this client
    r = await db.execute(
        select(Dette).where(
            Dette.livreur_id == livreur.id,
            Dette.client_id == client_id,
            Dette.statut != "soldee_totalement",
        )
    )
    active_dettes = r.scalars().all()

    result = []
    for tournee_id, lvs in groups.items():
        tournee = lvs[0].tournee
        total_du = sum(float(lv.montant_du) for lv in lvs)
        lv_ids = [lv.id for lv in lvs]
        lv_ids_set = set(lv_ids)
        nb_pains_nets = sum(lv.nb_pains_livres - lv.nb_pains_retournes for lv in lvs)

        # Check for active dette linked to this tournée's livraisons
        dette_found = None
        for dette in active_dettes:
            try:
                dette_lv_ids = set(json.loads(dette.livraison_ids or "[]"))
            except (ValueError, TypeError):
                dette_lv_ids = set()
            if dette_lv_ids & lv_ids_set:
                dette_found = dette
                break

        montant_restant = float(dette_found.montant_restant) if dette_found else total_du
        montant_deja_paye = total_du - montant_restant

        result.append(PendingTourneeResponse(
            tournee_id=tournee_id,
            tournee_date=str(tournee.date) if tournee else "",
            tournee_periode=tournee.periode if tournee else "",
            livraison_ids=lv_ids,
            total_montant_du=total_du,
            montant_deja_paye=montant_deja_paye,
            montant_restant=montant_restant,
            dette_id=dette_found.id if dette_found else None,
            nb_pains_nets=nb_pains_nets,
        ))

    # Sort by date desc
    result.sort(key=lambda x: x.tournee_date, reverse=True)
    return result


@router.get("/pending", response_model=list[PendingLivraisonResponse])
async def get_pending_livraisons(
    client_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_encaissements")),
):
    livraisons = await crud_livraison.get_unpaid_by_client(db, livreur.id, client_id=client_id)
    return [
        PendingLivraisonResponse(
            client_id=lv.client_id,
            client_nom=lv.client.nom if lv.client else "",
            livraison_id=lv.id,
            tournee_id=lv.tournee_id,
            tournee_date=str(lv.tournee.date) if lv.tournee else "",
            tournee_periode=lv.tournee.periode if lv.tournee else "",
            montant_du=float(lv.montant_du),
            nb_pains_livres=lv.nb_pains_livres,
            nb_pains_retournes=lv.nb_pains_retournes,
        )
        for lv in livraisons
    ]


@router.get("/{encaissement_id}", response_model=EncaissementResponse)
async def get_encaissement(
    encaissement_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_encaissements")),
):
    enc = await crud_encaissement.get_by_livreur_and_id(db, livreur.id, encaissement_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encaissement introuvable")
    return _serialize(enc)
