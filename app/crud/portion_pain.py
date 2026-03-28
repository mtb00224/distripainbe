from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.portion_pain import PortionPain

DEFAULT_PORTIONS = [
    {"nom": "Morceau 50 FCFA", "prix_fcfa": 50},
    {"nom": "Morceau 75 FCFA", "prix_fcfa": 75},
    {"nom": "Morceau 100 FCFA", "prix_fcfa": 100},
    {"nom": "Pain entier 150 FCFA", "prix_fcfa": 150},
]


class CRUDPortionPain(CRUDBase[PortionPain]):
    async def get_by_livreur(
        self, db: AsyncSession, livreur_id: int, include_inactive: bool = False
    ) -> list[PortionPain]:
        stmt = select(PortionPain).where(PortionPain.livreur_id == livreur_id)
        if not include_inactive:
            stmt = stmt.where(PortionPain.is_active == True)
        stmt = stmt.order_by(PortionPain.prix_fcfa)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, portion_id: int
    ) -> PortionPain | None:
        result = await db.execute(
            select(PortionPain).where(
                PortionPain.id == portion_id,
                PortionPain.livreur_id == livreur_id,
            )
        )
        return result.scalar_one_or_none()

    async def ensure_defaults(self, db: AsyncSession, livreur_id: int) -> None:
        """Create default portions for a livreur if they have none."""
        existing = await self.get_by_livreur(db, livreur_id, include_inactive=True)
        if not existing:
            for p in DEFAULT_PORTIONS:
                db.add(PortionPain(livreur_id=livreur_id, **p))
            await db.commit()


crud_portion = CRUDPortionPain(PortionPain)
