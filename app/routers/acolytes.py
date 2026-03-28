import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_context, livreur_only, require_permission
from app.core.security import hash_password, verify_password
from app.crud.acolyte import crud_acolyte
from app.db.session import get_db
from app.models.livreur import Livreur
from app.schemas.acolyte import AcolyteCreate, AcolyteResponse, AcolyteUpdate, AVAILABLE_PERMISSIONS
from app.schemas.auth import ChangePasswordRequest

router = APIRouter(prefix="/acolytes", tags=["acolytes"])

MAX_ACOLYTES = 2


def _serialize(acolyte) -> AcolyteResponse:
    try:
        perms = json.loads(acolyte.permissions or "[]")
    except (ValueError, TypeError):
        perms = []
    return AcolyteResponse(
        id=acolyte.id,
        livreur_principal_id=acolyte.livreur_principal_id,
        nom=acolyte.nom,
        email=acolyte.email,
        permissions=perms,
        is_default_password=acolyte.is_default_password,
        is_active=acolyte.is_active,
        created_at=acolyte.created_at,
    )


@router.get("", response_model=list[AcolyteResponse])
async def list_acolytes(
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(livreur_only()),
):
    acolytes = await crud_acolyte.get_by_livreur(db, livreur.id)
    return [_serialize(a) for a in acolytes]


@router.post("", response_model=AcolyteResponse, status_code=status.HTTP_201_CREATED)
async def create_acolyte(
    payload: AcolyteCreate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(livreur_only()),
):
    count = await crud_acolyte.count_by_livreur(db, livreur.id)
    if count >= MAX_ACOLYTES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_ACOLYTES} acolytes autorisés")

    if await crud_acolyte.get_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    invalid = [p for p in payload.permissions if p not in AVAILABLE_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Permissions invalides: {invalid}")

    acolyte = await crud_acolyte.create_acolyte(
        db,
        livreur_principal_id=livreur.id,
        nom=payload.nom,
        email=payload.email,
        permissions=payload.permissions,
    )
    return _serialize(acolyte)


@router.get("/{acolyte_id}", response_model=AcolyteResponse)
async def get_acolyte(
    acolyte_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(livreur_only()),
):
    a = await crud_acolyte.get_by_livreur_and_id(db, livreur.id, acolyte_id)
    if not a:
        raise HTTPException(status_code=404, detail="Acolyte introuvable")
    return _serialize(a)


@router.put("/{acolyte_id}", response_model=AcolyteResponse)
async def update_acolyte(
    acolyte_id: int,
    payload: AcolyteUpdate,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(livreur_only()),
):
    a = await crud_acolyte.get_by_livreur_and_id(db, livreur.id, acolyte_id)
    if not a:
        raise HTTPException(status_code=404, detail="Acolyte introuvable")

    updates = payload.model_dump(exclude_unset=True)
    if "permissions" in updates:
        invalid = [p for p in updates["permissions"] if p not in AVAILABLE_PERMISSIONS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Permissions invalides: {invalid}")
        updates["permissions"] = json.dumps(updates["permissions"])

    updated = await crud_acolyte.update(db, db_obj=a, obj_in=updates)
    return _serialize(updated)


@router.delete("/{acolyte_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_acolyte(
    acolyte_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(livreur_only()),
):
    a = await crud_acolyte.get_by_livreur_and_id(db, livreur.id, acolyte_id)
    if not a:
        raise HTTPException(status_code=404, detail="Acolyte introuvable")
    await crud_acolyte.update(db, db_obj=a, obj_in={"is_active": False})


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_acolyte_password(
    payload: ChangePasswordRequest,
    context=Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
):
    livreur, acolyte = context
    if acolyte is None:
        raise HTTPException(status_code=403, detail="Endpoint réservé aux acolytes")

    if not verify_password(payload.current_password, acolyte.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

    await crud_acolyte.update(db, db_obj=acolyte, obj_in={
        "password_hash": hash_password(payload.new_password),
        "is_default_password": False,
    })
