import json
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.livreur import AcolyteLivreur
from app.models.user import User, UserRole
from app.core.security import hash_password

DEFAULT_ACOLYTE_PASSWORD = "acolyte123"


class CRUDAcolyte(CRUDBase[AcolyteLivreur]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[AcolyteLivreur]:
        result = await db.execute(
            select(AcolyteLivreur)
            .join(User, AcolyteLivreur.user_id == User.id)
            .options(selectinload(AcolyteLivreur.user))
            .where(User.email == email, User.role == UserRole.ACOLYTE_LIVREUR)
        )
        return result.scalar_one_or_none()

    async def get_by_livreur(self, db: AsyncSession, livreur_id: int) -> list[AcolyteLivreur]:
        result = await db.execute(
            select(AcolyteLivreur)
            .options(selectinload(AcolyteLivreur.user))
            .where(
                AcolyteLivreur.livreur_principal_id == livreur_id,
                AcolyteLivreur.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def count_by_livreur(self, db: AsyncSession, livreur_id: int) -> int:
        result = await db.execute(
            select(func.count()).where(
                AcolyteLivreur.livreur_principal_id == livreur_id,
                AcolyteLivreur.is_active == True,
            )
        )
        return result.scalar_one()

    async def create_acolyte(
        self,
        db: AsyncSession,
        *,
        livreur_principal_id: int,
        first_name: str,
        last_name: str,
        username: str,
        email: Optional[str],
        phone_number: Optional[str] = None,
        permissions: list[str],
    ) -> AcolyteLivreur:
        user = User(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            phone_number=phone_number or "",
            role=UserRole.ACOLYTE_LIVREUR,
            password_hash=hash_password(DEFAULT_ACOLYTE_PASSWORD),
            must_change_password=True,
        )
        db.add(user)
        await db.flush()

        acolyte = AcolyteLivreur(
            user_id=user.id,
            livreur_principal_id=livreur_principal_id,
            permissions=json.dumps(permissions),
        )
        db.add(acolyte)
        await db.commit()

        result = await db.execute(
            select(AcolyteLivreur)
            .options(selectinload(AcolyteLivreur.user))
            .where(AcolyteLivreur.id == acolyte.id)
        )
        return result.scalar_one()

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, acolyte_id: int
    ) -> Optional[AcolyteLivreur]:
        result = await db.execute(
            select(AcolyteLivreur)
            .options(selectinload(AcolyteLivreur.user))
            .where(
                AcolyteLivreur.id == acolyte_id,
                AcolyteLivreur.livreur_principal_id == livreur_id,
            )
        )
        return result.scalar_one_or_none()


crud_acolyte = CRUDAcolyte(AcolyteLivreur)
