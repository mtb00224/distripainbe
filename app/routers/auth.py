import json
from datetime import datetime, timedelta, timezone

import pydantic
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
from app.crud.livreur import crud_livreur
from app.db.session import get_db
from app.models.boulangerie import AdminBoulangerie, Boulangerie
from app.models.livreur import Livreur, AcolyteLivreur
from app.models.livreur_interne import LivreurInterne
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole, UserSession
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


async def _store_refresh_token(db: AsyncSession, raw_token: str, user_id: int) -> None:
    expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        token_hash=hash_refresh_token(raw_token),
        user_id=user_id,
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
    """Inscription unifiée — livreur ou admin_boulangerie selon le champ `role`."""
    existing_email = await db.execute(select(User).where(User.email == payload.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    existing_username = await db.execute(select(User).where(User.username == payload.username))
    if existing_username.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")

    # ── Auto-rattachement téléphone → LivreurInterne ─────────────────────────
    async def _auto_link_livreur_interne(user_id: int, phone: str | None) -> None:
        """Si le numéro de téléphone correspond à un LivreurInterne sans compte, on le rattache."""
        if not phone:
            return
        result = await db.execute(
            select(LivreurInterne).where(
                LivreurInterne.telephone == phone,
                LivreurInterne.user_id == None,
            )
        )
        li = result.scalar_one_or_none()
        if li:
            li.user_id = user_id
            db.add(li)

    # ── Livreur ──────────────────────────────────────────────────────────────
    if payload.role == "livreur":
        livreur = await crud_livreur.create_livreur(
            db,
            first_name=payload.first_name,
            last_name=payload.last_name,
            username=payload.username,
            email=payload.email,
            password=payload.password,
            phone_number=payload.phone_number,
        )
        access_token = create_access_token({
            "sub": str(livreur.user_id),
            "role": "livreur",
            "livreur_id": livreur.id,
        })
        await _auto_link_livreur_interne(livreur.user_id, payload.phone_number)
        refresh_raw = generate_refresh_token()
        await _store_refresh_token(db, refresh_raw, livreur.user_id)
        _set_refresh_cookie(response, refresh_raw)
        return TokenResponse(access_token=access_token, role="livreur")

    # ── AdminBoulangerie ──────────────────────────────────────────────────────
    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=payload.email,
        phone_number=payload.phone_number or "",
        role=UserRole.ADMIN_BOULANGERIE,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    admin_b = AdminBoulangerie(user_id=user.id)
    db.add(admin_b)
    await db.flush()
    await _auto_link_livreur_interne(user.id, payload.phone_number)
    await db.commit()

    access_token = create_access_token({
        "sub": str(user.id),
        "role": "admin_boulangerie",
        "admin_boulangerie_id": admin_b.id,
        "boulangerie_active_id": None,
    })
    return TokenResponse(
        access_token=access_token,
        role="admin_boulangerie",
        admin_boulangerie_id=admin_b.id,
        boulangerie_active_id=None,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # Cherche le User par email
    result = await db.execute(
        select(User).where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    # Track session
    ua = request.headers.get("user-agent")
    device_type, platform, browser = detect_device(ua)
    xff = request.headers.get("X-Forwarded-For")
    ip = (xff.split(",")[0].strip() if xff else (
        request.client.host if request.client else "unknown"
    ))[:45]
    db.add(UserSession(
        user_id=user.id,
        device_type=device_type,
        platform=platform,
        browser=browser,
        ip_address=ip,
    ))

    if user.role == UserRole.LIVREUR:
        livreur_result = await db.execute(
            select(Livreur).where(Livreur.user_id == user.id)
        )
        livreur = livreur_result.scalar_one_or_none()
        if not livreur:
            raise HTTPException(status_code=500, detail="Profil livreur introuvable")

        access_token = create_access_token({
            "sub": str(user.id),
            "role": "livreur",
            "livreur_id": livreur.id,
        })
        refresh_raw = generate_refresh_token()
        await _store_refresh_token(db, refresh_raw, user.id)
        _set_refresh_cookie(response, refresh_raw)
        await db.commit()
        return TokenResponse(access_token=access_token, role="livreur")

    if user.role == UserRole.ACOLYTE_LIVREUR:
        acolyte_result = await db.execute(
            select(AcolyteLivreur).where(AcolyteLivreur.user_id == user.id)
        )
        acolyte = acolyte_result.scalar_one_or_none()
        if not acolyte or not acolyte.is_active:
            raise HTTPException(status_code=403, detail="Compte acolyte désactivé")

        access_token = create_access_token({
            "sub": str(user.id),
            "role": "acolyte_livreur",
            "livreur_id": acolyte.livreur_principal_id,
            "acolyte_id": acolyte.id,
        })
        refresh_raw = generate_refresh_token()
        await _store_refresh_token(db, refresh_raw, user.id)
        _set_refresh_cookie(response, refresh_raw)
        await db.commit()
        return TokenResponse(
            access_token=access_token,
            role="acolyte_livreur",
            must_change_password=user.must_change_password,
        )

    if user.role == UserRole.ADMIN_BOULANGERIE:
        ab_result = await db.execute(
            select(AdminBoulangerie)
            .options(selectinload(AdminBoulangerie.boulangeries))
            .where(AdminBoulangerie.user_id == user.id)
        )
        admin_b = ab_result.scalar_one_or_none()
        if not admin_b:
            raise HTTPException(status_code=500, detail="Profil admin boulangerie introuvable")

        actives = [b for b in admin_b.boulangeries if b.is_active]
        boulangerie_id = actives[0].id if actives else None

        access_token = create_access_token({
            "sub": str(user.id),
            "role": "admin_boulangerie",
            "admin_boulangerie_id": admin_b.id,
            "boulangerie_active_id": boulangerie_id,
        })
        refresh_raw = generate_refresh_token()
        await _store_refresh_token(db, refresh_raw, user.id)
        _set_refresh_cookie(response, refresh_raw)
        await db.commit()
        return TokenResponse(
            access_token=access_token,
            role="admin_boulangerie",
            admin_boulangerie_id=admin_b.id,
            boulangerie_active_id=boulangerie_id,
        )

    raise HTTPException(status_code=403, detail="Ce compte ne peut pas se connecter ici")


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

    # Rotation du refresh token
    rt.is_revoked = True
    db.add(rt)

    new_refresh = generate_refresh_token()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_rt = RefreshToken(
        token_hash=hash_refresh_token(new_refresh),
        user_id=rt.user_id,
        expires_at=expires,
    )
    db.add(new_rt)

    # Charger le User pour connaître son rôle
    user_result = await db.execute(
        select(User).where(User.id == rt.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Compte introuvable ou désactivé")

    if user.role == UserRole.LIVREUR:
        livreur_result = await db.execute(
            select(Livreur).where(Livreur.user_id == user.id)
        )
        livreur = livreur_result.scalar_one_or_none()
        if not livreur:
            raise HTTPException(status_code=401, detail="Profil livreur introuvable")
        access_token = create_access_token({
            "sub": str(user.id),
            "role": "livreur",
            "livreur_id": livreur.id,
        })
    elif user.role == UserRole.ACOLYTE_LIVREUR:
        acolyte_result = await db.execute(
            select(AcolyteLivreur).where(AcolyteLivreur.user_id == user.id)
        )
        acolyte = acolyte_result.scalar_one_or_none()
        if not acolyte:
            raise HTTPException(status_code=401, detail="Profil acolyte introuvable")
        access_token = create_access_token({
            "sub": str(user.id),
            "role": "acolyte_livreur",
            "livreur_id": acolyte.livreur_principal_id,
            "acolyte_id": acolyte.id,
        })
    elif user.role == UserRole.ADMIN_BOULANGERIE:
        ab_result = await db.execute(
            select(AdminBoulangerie)
            .options(selectinload(AdminBoulangerie.boulangeries))
            .where(AdminBoulangerie.user_id == user.id)
        )
        admin_b = ab_result.scalar_one_or_none()
        if not admin_b:
            raise HTTPException(status_code=401, detail="Profil admin boulangerie introuvable")
        actives = [b for b in admin_b.boulangeries if b.is_active]
        boulangerie_id = actives[0].id if actives else None
        access_token = create_access_token({
            "sub": str(user.id),
            "role": "admin_boulangerie",
            "admin_boulangerie_id": admin_b.id,
            "boulangerie_active_id": boulangerie_id,
        })
    else:
        raise HTTPException(status_code=401, detail="Rôle non supporté pour ce refresh")

    await db.commit()
    _set_refresh_cookie(response, new_refresh)
    extra: dict = {}
    if user.role == UserRole.ADMIN_BOULANGERIE:
        extra["role"] = "admin_boulangerie"
        extra["admin_boulangerie_id"] = admin_b.id
        extra["boulangerie_active_id"] = boulangerie_id
    return RefreshResponse(access_token=access_token, **extra)


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
):
    livreur, acolyte = context
    if acolyte is None:
        return CurrentUserResponse(
            id=livreur.user.id,
            first_name=livreur.user.first_name,
            last_name=livreur.user.last_name,
            username=livreur.user.username,
            email=livreur.user.email,
            phone_number=livreur.user.phone_number,
            role="livreur",
            is_active=livreur.user.is_active,
            livreur_id=livreur.id,
        )
    try:
        permissions = json.loads(acolyte.permissions or "[]")
    except (ValueError, TypeError):
        permissions = []
    return CurrentUserResponse(
        id=acolyte.user.id,
        first_name=acolyte.user.first_name,
        last_name=acolyte.user.last_name,
        username=acolyte.user.username,
        email=acolyte.user.email,
        phone_number=acolyte.user.phone_number,
        role="acolyte_livreur",
        is_active=acolyte.user.is_active,
        permissions=permissions,
        livreur_id=livreur.id,
        livreur_principal_id=acolyte.livreur_principal_id,
    )


@router.patch("/me", response_model=CurrentUserResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    context=Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
):
    livreur, acolyte = context
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")

    target_user = acolyte.user if acolyte else livreur.user
    for field, value in updates.items():
        setattr(target_user, field, value)
    db.add(target_user)
    await db.commit()

    return await get_me(context)


class ForgotPasswordCheckRequest(pydantic.BaseModel):
    email: str


class ForgotPasswordResetRequest(pydantic.BaseModel):
    email: str
    new_password: str


@router.post("/forgot-password/check", status_code=200)
async def forgot_password_check(
    payload: ForgotPasswordCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Vérifie qu'un email existe (livreur ou admin boulangerie). Retourne le rôle trouvé."""
    result = await db.execute(
        select(User).where(User.email == payload.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or user.role not in (UserRole.LIVREUR, UserRole.ADMIN_BOULANGERIE):
        raise HTTPException(status_code=404, detail="Aucun compte trouvé avec cet email")
    return {"role": user.role.value}


@router.post("/forgot-password/reset", status_code=204)
async def forgot_password_reset(
    payload: ForgotPasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Réinitialise le mot de passe d'un livreur ou admin boulangerie par email."""
    if len(payload.new_password) < 5:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 5 caractères")
    result = await db.execute(
        select(User).where(User.email == payload.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or user.role not in (UserRole.LIVREUR, UserRole.ADMIN_BOULANGERIE):
        raise HTTPException(status_code=404, detail="Aucun compte trouvé avec cet email")
    user.password_hash = hash_password(payload.new_password)
    await db.commit()


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_livreur_password(
    payload: ChangePasswordLivreurRequest,
    context=Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
):
    """Change le mot de passe du livreur courant."""
    livreur, acolyte = context
    if acolyte is not None:
        raise HTTPException(
            status_code=403,
            detail="Utilisez /acolytes/me/password pour les acolytes",
        )

    if not verify_password(payload.current_password, livreur.user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

    livreur.user.password_hash = hash_password(payload.new_password)
    db.add(livreur.user)
    await db.commit()
