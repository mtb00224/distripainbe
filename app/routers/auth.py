import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.dependencies import get_current_user_context
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.crud.acolyte import crud_acolyte
from app.crud.livreur import crud_livreur
from app.db.session import get_db
from app.models.acolyte import Acolyte
from app.models.livreur import Livreur
from app.models.refresh_token import RefreshToken
from app.models.user_session import UserSession
from app.utils.device_detection import detect_device
from app.schemas.auth import (
    ChangePasswordLivreurRequest,
    ChangePasswordRequest,
    CurrentUserResponse,
    LoginRequest,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )


async def _store_refresh_token(
    db: AsyncSession, raw_token: str, user_id: int, user_type: str
) -> None:
    expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        token_hash=hash_refresh_token(raw_token),
        user_id=user_id,
        user_type=user_type,
        expires_at=expires,
    )
    db.add(rt)
    await db.commit()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if await crud_livreur.get_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    livreur = await crud_livreur.create_livreur(
        db,
        nom=payload.nom,
        email=payload.email,
        password=payload.password,
        telephone=payload.telephone,
    )

    access_token = create_access_token({"sub": str(livreur.id), "user_type": "livreur"})
    refresh_raw = generate_refresh_token()
    await _store_refresh_token(db, refresh_raw, livreur.id, "livreur")
    _set_refresh_cookie(response, refresh_raw)

    return TokenResponse(access_token=access_token, user_type="livreur")


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # Try livreur first
    livreur = await crud_livreur.get_by_email(db, payload.email)
    if livreur and verify_password(payload.password, livreur.password_hash):
        if not livreur.is_active:
            raise HTTPException(status_code=403, detail="Compte désactivé")
        access_token = create_access_token({"sub": str(livreur.id), "user_type": "livreur"})
        refresh_raw = generate_refresh_token()
        await _store_refresh_token(db, refresh_raw, livreur.id, "livreur")
        _set_refresh_cookie(response, refresh_raw)
        # Track session
        ua = request.headers.get("user-agent")
        device_type, platform, browser = detect_device(ua)
        xff = request.headers.get("X-Forwarded-For")
        ip = (xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown"))[:45]
        db.add(UserSession(
            livreur_id=livreur.id,
            user_type="livreur",
            device_type=device_type,
            platform=platform,
            browser=browser,
            ip_address=ip,
            user_agent=(ua or "")[:512],
        ))
        await db.commit()
        return TokenResponse(access_token=access_token, user_type="livreur")

    # Try acolyte
    acolyte = await crud_acolyte.get_by_email(db, payload.email)
    if acolyte and verify_password(payload.password, acolyte.password_hash):
        if not acolyte.is_active:
            raise HTTPException(status_code=403, detail="Compte désactivé")
        access_token = create_access_token({
            "sub": str(acolyte.id),
            "user_type": "acolyte",
            "livreur_principal_id": acolyte.livreur_principal_id,
        })
        refresh_raw = generate_refresh_token()
        await _store_refresh_token(db, refresh_raw, acolyte.id, "acolyte")
        _set_refresh_cookie(response, refresh_raw)
        # Track session for the livreur principal
        ua = request.headers.get("user-agent")
        device_type, platform, browser = detect_device(ua)
        xff = request.headers.get("X-Forwarded-For")
        ip = (xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown"))[:45]
        db.add(UserSession(
            livreur_id=acolyte.livreur_principal_id,
            user_type="acolyte",
            acolyte_id=acolyte.id,
            device_type=device_type,
            platform=platform,
            browser=browser,
            ip_address=ip,
            user_agent=(ua or "")[:512],
        ))
        await db.commit()
        return TokenResponse(
            access_token=access_token,
            user_type="acolyte",
            must_change_password=acolyte.is_default_password,
        )

    raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Token de rafraîchissement manquant")

    token_hash = hash_refresh_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
        )
    )
    rt = result.scalar_one_or_none()
    if not rt or rt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expiré ou révoqué")

    # Rotate refresh token
    rt.is_revoked = True
    db.add(rt)

    new_refresh = generate_refresh_token()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_rt = RefreshToken(
        token_hash=hash_refresh_token(new_refresh),
        user_id=rt.user_id,
        user_type=rt.user_type,
        expires_at=expires,
    )
    db.add(new_rt)
    await db.commit()

    if rt.user_type == "livreur":
        access_token = create_access_token({"sub": str(rt.user_id), "user_type": "livreur"})
    else:
        result2 = await db.execute(select(Acolyte).where(Acolyte.id == rt.user_id))
        acolyte = result2.scalar_one_or_none()
        if not acolyte:
            raise HTTPException(status_code=401, detail="Acolyte introuvable")
        access_token = create_access_token({
            "sub": str(acolyte.id),
            "user_type": "acolyte",
            "livreur_principal_id": acolyte.livreur_principal_id,
        })

    _set_refresh_cookie(response, new_refresh)
    return RefreshResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        token_hash = hash_refresh_token(refresh_token)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt:
            rt.is_revoked = True
            db.add(rt)
            await db.commit()

    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
    return {"message": "Déconnexion réussie"}


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    context=Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
):
    livreur, acolyte = context
    if acolyte is None:
        # Reload with pays relationship
        result = await db.execute(
            select(Livreur).options(selectinload(Livreur.pays)).where(Livreur.id == livreur.id)
        )
        livreur = result.scalar_one()
        return CurrentUserResponse(
            id=livreur.id,
            nom=livreur.nom,
            email=livreur.email,
            telephone=livreur.telephone,
            user_type="livreur",
            is_active=livreur.is_active,
            pays=livreur.pays,
        )
    try:
        permissions = json.loads(acolyte.permissions or "[]")
    except (ValueError, TypeError):
        permissions = []
    return CurrentUserResponse(
        id=acolyte.id,
        nom=acolyte.nom,
        email=acolyte.email,
        user_type="acolyte",
        permissions=permissions,
        livreur_principal_id=acolyte.livreur_principal_id,
        is_active=acolyte.is_active,
    )


@router.patch("/me", response_model=CurrentUserResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    context=Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
):
    """Update nom and telephone for the current user (livreur or acolyte)."""
    livreur, acolyte = context
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")

    if acolyte is None:
        await crud_livreur.update(db, db_obj=livreur, obj_in=updates)
        refreshed = await crud_livreur.get(db, livreur.id)
        return CurrentUserResponse(
            id=refreshed.id,
            nom=refreshed.nom,
            email=refreshed.email,
            telephone=refreshed.telephone,
            user_type="livreur",
            is_active=refreshed.is_active,
        )
    else:
        await crud_acolyte.update(db, db_obj=acolyte, obj_in=updates)
        refreshed = await crud_acolyte.get(db, acolyte.id)
        try:
            permissions = json.loads(refreshed.permissions or "[]")
        except (ValueError, TypeError):
            permissions = []
        return CurrentUserResponse(
            id=refreshed.id,
            nom=refreshed.nom,
            email=refreshed.email,
            user_type="acolyte",
            permissions=permissions,
            livreur_principal_id=refreshed.livreur_principal_id,
            is_active=refreshed.is_active,
        )


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_livreur_password(
    payload: ChangePasswordLivreurRequest,
    context=Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
):
    """Change password for the current livreur."""
    livreur, acolyte = context
    if acolyte is not None:
        raise HTTPException(status_code=403, detail="Utilisez /acolytes/me/password pour les acolytes")

    if not verify_password(payload.current_password, livreur.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

    await crud_livreur.update(db, db_obj=livreur, obj_in={
        "password_hash": hash_password(payload.new_password),
    })
