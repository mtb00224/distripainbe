from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.client import Client


class CRUDClient(CRUDBase[Client]):
    async def get_by_livreur(
        self,
        db: AsyncSession,
        livreur_id: int,
        zone_id: Optional[int] = None,
        search: Optional[str] = None,
        include_inactive: bool = False,
    ) -> list[Client]:
        stmt = (
            select(Client)
            .options(selectinload(Client.zone))
            .where(Client.livreur_id == livreur_id)
        )
        if not include_inactive:
            stmt = stmt.where(Client.is_active == True)
        if zone_id:
            stmt = stmt.where(Client.zone_id == zone_id)
        if search:
            stmt = stmt.where(Client.nom.ilike(f"%{search}%"))
        stmt = stmt.order_by(Client.nom)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, client_id: int
    ) -> Optional[Client]:
        result = await db.execute(
            select(Client)
            .options(selectinload(Client.zone))
            .where(Client.id == client_id, Client.livreur_id == livreur_id)
        )
        return result.scalar_one_or_none()

    async def update_solde(
        self, db: AsyncSession, client_id: int, delta: Decimal
    ) -> None:
        """Add delta (positive = client owes more, negative = client paid)."""
        result = await db.execute(select(Client).where(Client.id == client_id))
        client = result.scalar_one_or_none()
        if client:
            client.solde_actuel = (client.solde_actuel or Decimal("0")) + delta
            db.add(client)
            await db.commit()


crud_client = CRUDClient(Client)
