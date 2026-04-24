import json
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.security import decode_token
from app.db.session import get_db
from app.models.livreur import Livreur, AcolyteLivreur
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def _get_livreur_by_id(db: AsyncSession, livreur_id: int) -> Livreur:
    result = await db.execute(
        select(Livreur)
        .options(selectinload(Livreur.user))
        .where(Livreur.id == livreur_id)
    )
    livreur = result.scalar_one_or_none()
    if not livreur or not livreur.user or not livreur.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte introuvable ou désactivé",
        )
    return livreur


async def _get_acolyte_by_id(db: AsyncSession, acolyte_id: int) -> AcolyteLivreur:
    result = await db.execute(
        select(AcolyteLivreur)
        .options(selectinload(AcolyteLivreur.user))
        .where(AcolyteLivreur.id == acolyte_id)
    )
    acolyte = result.scalar_one_or_none()
    if not acolyte or not acolyte.user or not acolyte.user.is_active or not acolyte.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte acolyte introuvable ou désactivé",
        )
    return acolyte


async def get_current_user_context(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Livreur, Optional[AcolyteLivreur]]:
    """
    Retourne (livreur_principal, acolyte_ou_None).
    Valide les tokens livreur et acolyte_livreur.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        role: str = payload.get("role")
        sub: str = payload.get("sub")
        if not role or not sub:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if role == "livreur":
        livreur_id = payload.get("livreur_id")
        if livreur_id is None:
            raise credentials_exception
        livreur = await _get_livreur_by_id(db, int(livreur_id))
        return livreur, None

    if role == "acolyte_livreur":
        acolyte_id = payload.get("acolyte_id")
        livreur_id = payload.get("livreur_id")
        if acolyte_id is None or livreur_id is None:
            raise credentials_exception
        acolyte = await _get_acolyte_by_id(db, int(acolyte_id))
        livreur = await _get_livreur_by_id(db, int(livreur_id))
        return livreur, acolyte

    raise credentials_exception


async def get_current_livreur(
    context: Tuple[Livreur, Optional[AcolyteLivreur]] = Depends(get_current_user_context),
) -> Livreur:
    """Retourne le livreur principal (propriétaire des données). Valide pour livreur et acolyte."""
    livreur, _ = context
    return livreur


async def get_current_acolyte_context(
    context: Tuple[Livreur, Optional[AcolyteLivreur]] = Depends(get_current_user_context),
) -> Tuple[Livreur, Optional[AcolyteLivreur]]:
    return context


_PERMISSION_MESSAGES: dict[str, str] = {
    "read_clients": "consulter la liste des clients",
    "write_clients": "ajouter ou modifier des clients",
    "read_boulangeries": "consulter les boulangeries",
    "write_boulangeries": "ajouter ou modifier des boulangeries",
    "read_zones": "consulter les zones",
    "write_zones": "ajouter ou modifier des zones",
    "read_tournees": "consulter les tournées",
    "create_tournees": "créer une nouvelle tournée",
    "update_tournees": "modifier les chiffres d'une tournée",
    "terminer_tournees": "clôturer une tournée",
    "write_livraisons": "gérer les livraisons d'une tournée",
    "read_encaissements": "consulter les encaissements",
    "write_encaissements": "enregistrer un paiement",
    "read_stats": "consulter les statistiques",
}


def require_permission(permission: str):
    """Vérifie que l'utilisateur courant a la permission requise.
    Le livreur principal passe toujours. Les acolytes doivent avoir la permission."""

    async def _check(
        context: Tuple[Livreur, Optional[AcolyteLivreur]] = Depends(get_current_user_context),
    ) -> Livreur:
        livreur, acolyte = context
        action = _PERMISSION_MESSAGES.get(permission, permission)

        # Restrictions admin-plateforme sur le livreur (None = accès libre)
        if livreur.permissions is not None:
            try:
                livreur_perms: list[str] = json.loads(livreur.permissions)
            except (ValueError, TypeError):
                livreur_perms = []
            if permission not in livreur_perms:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"L'accès à « {action} » a été restreint par l'administrateur.",
                )

        if acolyte is None:
            return livreur

        # Permissions de l'acolyte
        try:
            acolyte_perms: list[str] = json.loads(acolyte.permissions or "[]")
        except (ValueError, TypeError):
            acolyte_perms = []
        if permission not in acolyte_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Vous n'avez pas le droit de {action}. Demandez cette permission à votre livreur.",
            )
        return livreur

    return _check


def livreur_only():
    """Bloque les acolytes — seul le livreur principal est autorisé."""

    async def _check(
        context: Tuple[Livreur, Optional[AcolyteLivreur]] = Depends(get_current_user_context),
    ) -> Livreur:
        livreur, acolyte = context
        if acolyte is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seul le livreur principal peut effectuer cette action",
            )
        return livreur

    return _check
