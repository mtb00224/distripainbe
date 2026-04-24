import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user_context, livreur_only
from app.core.security import hash_password, verify_password
from app.crud.acolyte import crud_acolyte
from app.db.session import get_db
from app.models.livreur import Livreur, AcolyteLivreur
from app.models.user import User
from app.schemas.acolyte import (
    AcolyteCreate, AcolyteResponse, AcolyteUpdate, AVAILABLE_PERMISSIONS
)
from app.schemas.auth import ChangePasswordRequest

router = APIRouter(prefix="/acolytes", tags=["acolytes"])

MAX_ACOLYTES = 2


def _serialize(acolyte: AcolyteLivreur) -> AcolyteResponse:
    return AcolyteResponse.model_validate(acolyte)


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
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_ACOLYTES} acolytes autorisés",
        )

    # Vérifier username/email unique
    existing_u = await db.execute(select(User).where(User.username == payload.username))
    if existing_u.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")
    if payload.email:
        existing_e = await db.execute(select(User).where(User.email == payload.email))
        if existing_e.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email déjà utilisé")

    acolyte = await crud_acolyte.create_acolyte(
        db,
        livreur_principal_id=livreur.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=payload.email,
        phone_number=payload.phone_number,
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

    if "is_active" in updates:
        a.is_active = updates["is_active"]
        db.add(a)
    if "permissions" in updates:
        a.permissions = updates["permissions"]
        db.add(a)
    await db.commit()

    result = await db.execute(
        select(AcolyteLivreur)
        .options(selectinload(AcolyteLivreur.user))
        .where(AcolyteLivreur.id == a.id)
    )
    return _serialize(result.scalar_one())


@router.delete("/{acolyte_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_acolyte(
    acolyte_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(livreur_only()),
):
    a = await crud_acolyte.get_by_livreur_and_id(db, livreur.id, acolyte_id)
    if not a:
        raise HTTPException(status_code=404, detail="Acolyte introuvable")
    a.is_active = False
    db.add(a)
    await db.commit()


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_acolyte_password(
    payload: ChangePasswordRequest,
    context=Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
):
    livreur, acolyte = context
    if acolyte is None:
        raise HTTPException(status_code=403, detail="Endpoint réservé aux acolytes")

    if not verify_password(payload.current_password, acolyte.user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

    acolyte.user.password_hash = hash_password(payload.new_password)
    acolyte.user.must_change_password = False
    db.add(acolyte.user)
    await db.commit()
