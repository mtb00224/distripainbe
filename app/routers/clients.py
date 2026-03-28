from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_permission
from app.crud.client import crud_client
from app.db.session import get_db
from app.models.livreur import Livreur
from app.schemas.client import ClientCreate, ClientResponse, ClientSoldeResponse, ClientUpdate
from app.services.bilan_service import get_client_historique, get_payment_status

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    zone_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_clients")),
):
    return await crud_client.get_by_livreur(
        db, livreur.id, zone_id=zone_id, search=search, include_inactive=include_inactive
    )


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_clients")),
):
    client = await crud_client.create(db, obj_in={
        "livreur_id": livreur.id,
        "zone_id": payload.zone_id,
        "nom": payload.nom,
        "telephone": payload.telephone,
        "prix_vente_pain": payload.prix_vente_pain,
    })
    return await crud_client.get_by_livreur_and_id(db, livreur.id, client.id)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    return client


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    return await crud_client.update(db, db_obj=client, obj_in=payload.model_dump(exclude_unset=True))


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("write_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    await crud_client.update(db, db_obj=client, obj_in={"is_active": False})


@router.get("/{client_id}/solde", response_model=ClientSoldeResponse)
async def get_client_solde(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    return ClientSoldeResponse(
        client_id=client.id,
        nom=client.nom,
        solde_actuel=client.solde_actuel,
        statut=get_payment_status(client.solde_actuel),
    )


@router.get("/{client_id}/historique")
async def get_client_historique_endpoint(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_clients")),
):
    client = await crud_client.get_by_livreur_and_id(db, livreur.id, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    return await get_client_historique(db, livreur.id, client_id)
