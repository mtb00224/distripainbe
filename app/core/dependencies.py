import json
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import decode_token
from app.db.session import get_db
from app.models.livreur import Livreur
from app.models.acolyte import Acolyte

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def _get_livreur_by_id(db: AsyncSession, livreur_id: int) -> Livreur:
    result = await db.execute(select(Livreur).where(Livreur.id == livreur_id))
    livreur = result.scalar_one_or_none()
    if not livreur or not livreur.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte introuvable ou désactivé",
        )
    return livreur


async def _get_acolyte_by_id(db: AsyncSession, acolyte_id: int) -> Acolyte:
    result = await db.execute(select(Acolyte).where(Acolyte.id == acolyte_id))
    acolyte = result.scalar_one_or_none()
    if not acolyte or not acolyte.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte acolyte introuvable ou désactivé",
        )
    return acolyte


async def get_current_user_context(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Livreur, Optional[Acolyte]]:
    """
    Returns (livreur_principal, acolyte_or_None).
    If token belongs to a livreur: (livreur, None).
    If token belongs to an acolyte: (livreur_principal, acolyte).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_type: str = payload.get("user_type")
        sub: str = payload.get("sub")
        if user_type is None or sub is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if user_type == "livreur":
        livreur = await _get_livreur_by_id(db, int(sub))
        return livreur, None

    elif user_type == "acolyte":
        acolyte = await _get_acolyte_by_id(db, int(sub))
        livreur = await _get_livreur_by_id(db, acolyte.livreur_principal_id)
        return livreur, acolyte

    raise credentials_exception


async def get_current_livreur(
    context: Tuple[Livreur, Optional[Acolyte]] = Depends(get_current_user_context),
) -> Livreur:
    """Returns the principal livreur (owner of all data). Works for both livreurs and acolytes."""
    livreur, _ = context
    return livreur


async def get_current_acolyte_context(
    context: Tuple[Livreur, Optional[Acolyte]] = Depends(get_current_user_context),
) -> Tuple[Livreur, Optional[Acolyte]]:
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
    """Dependency factory — verifies that the current user has the given permission.
    Livreur principal always passes. Acolytes must have the permission in their JSON list."""

    async def _check(
        context: Tuple[Livreur, Optional[Acolyte]] = Depends(get_current_user_context),
    ) -> Livreur:
        livreur, acolyte = context
        action = _PERMISSION_MESSAGES.get(permission, permission)

        # Check livreur-level restrictions set by admin (None = unrestricted)
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

        # Check acolyte-level permissions
        try:
            acolyte_perms: list[str] = json.loads(acolyte.permissions or "[]")
        except (ValueError, TypeError):
            acolyte_perms = []
        if permission not in acolyte_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Vous n'avez pas le droit de {action}. Demandez cette permission à votre livreur principal.",
            )
        return livreur

    return _check


def livreur_only():
    """Dependency that blocks acolytes — only the principal livreur is allowed."""

    async def _check(
        context: Tuple[Livreur, Optional[Acolyte]] = Depends(get_current_user_context),
    ) -> Livreur:
        livreur, acolyte = context
        if acolyte is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seul le livreur principal peut effectuer cette action",
            )
        return livreur

    return _check
