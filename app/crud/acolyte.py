import json
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.acolyte import Acolyte
from app.core.security import hash_password, DEFAULT_ACOLYTE_PASSWORD


class CRUDAcolyte(CRUDBase[Acolyte]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[Acolyte]:
        result = await db.execute(select(Acolyte).where(Acolyte.email == email))
        return result.scalar_one_or_none()

    async def get_by_livreur(self, db: AsyncSession, livreur_id: int) -> list[Acolyte]:
        result = await db.execute(
            select(Acolyte).where(
                Acolyte.livreur_principal_id == livreur_id,
                Acolyte.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def count_by_livreur(self, db: AsyncSession, livreur_id: int) -> int:
        result = await db.execute(
            select(func.count()).where(
                Acolyte.livreur_principal_id == livreur_id,
                Acolyte.is_active == True,
            )
        )
        return result.scalar_one()

    async def create_acolyte(
        self,
        db: AsyncSession,
        *,
        livreur_principal_id: int,
        nom: str,
        email: str,
        permissions: list[str],
    ) -> Acolyte:
        acolyte = Acolyte(
            livreur_principal_id=livreur_principal_id,
            nom=nom,
            email=email,
            password_hash=hash_password(DEFAULT_ACOLYTE_PASSWORD),
            permissions=json.dumps(permissions),
            is_default_password=True,
        )
        db.add(acolyte)
        await db.commit()
        await db.refresh(acolyte)
        return acolyte

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, acolyte_id: int
    ) -> Optional[Acolyte]:
        result = await db.execute(
            select(Acolyte).where(
                Acolyte.id == acolyte_id,
                Acolyte.livreur_principal_id == livreur_id,
            )
        )
        return result.scalar_one_or_none()


crud_acolyte = CRUDAcolyte(Acolyte)
