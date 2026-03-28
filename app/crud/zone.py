from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.zone import Zone


class CRUDZone(CRUDBase[Zone]):
    async def get_by_livreur(self, db: AsyncSession, livreur_id: int) -> list[Zone]:
        result = await db.execute(select(Zone).where(Zone.livreur_id == livreur_id))
        return list(result.scalars().all())

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, zone_id: int
    ) -> Optional[Zone]:
        result = await db.execute(
            select(Zone).where(Zone.id == zone_id, Zone.livreur_id == livreur_id)
        )
        return result.scalar_one_or_none()


crud_zone = CRUDZone(Zone)
