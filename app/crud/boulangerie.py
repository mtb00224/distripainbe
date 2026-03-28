from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.boulangerie import Boulangerie


class CRUDBoulangerie(CRUDBase[Boulangerie]):
    async def get_by_livreur(
        self, db: AsyncSession, livreur_id: int, include_inactive: bool = False
    ) -> list[Boulangerie]:
        stmt = select(Boulangerie).where(Boulangerie.livreur_id == livreur_id)
        if not include_inactive:
            stmt = stmt.where(Boulangerie.is_active == True)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, boulangerie_id: int
    ) -> Optional[Boulangerie]:
        result = await db.execute(
            select(Boulangerie).where(
                Boulangerie.id == boulangerie_id,
                Boulangerie.livreur_id == livreur_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_default(self, db: AsyncSession, livreur_id: int) -> Optional[Boulangerie]:
        result = await db.execute(
            select(Boulangerie).where(
                Boulangerie.livreur_id == livreur_id,
                Boulangerie.is_default == True,
            )
        )
        return result.scalar_one_or_none()

    async def create_default(self, db: AsyncSession, livreur_id: int) -> Boulangerie:
        boulangerie = Boulangerie(
            livreur_id=livreur_id,
            nom="Boulangerie par défaut",
            is_default=True,
        )
        db.add(boulangerie)
        await db.commit()
        await db.refresh(boulangerie)
        return boulangerie


crud_boulangerie = CRUDBoulangerie(Boulangerie)
