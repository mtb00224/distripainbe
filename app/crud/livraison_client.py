from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.livraison_client import LivraisonClient
from app.models.client import Client
from app.models.tournee import Tournee


class CRUDLivraisonClient(CRUDBase[LivraisonClient]):
    async def get_by_tournee(
        self, db: AsyncSession, tournee_id: int
    ) -> list[LivraisonClient]:
        result = await db.execute(
            select(LivraisonClient)
            .options(selectinload(LivraisonClient.client).selectinload(Client.zone))
            .where(LivraisonClient.tournee_id == tournee_id)
        )
        return list(result.scalars().all())

    async def get_unpaid_by_client(
        self, db: AsyncSession, livreur_id: int, client_id: Optional[int] = None
    ) -> list[LivraisonClient]:
        stmt = (
            select(LivraisonClient)
            .join(Tournee, LivraisonClient.tournee_id == Tournee.id)
            .options(
                selectinload(LivraisonClient.client).selectinload(Client.zone),
                selectinload(LivraisonClient.tournee),
            )
            .where(
                LivraisonClient.livreur_id == livreur_id,
                LivraisonClient.is_paid == False,
                Tournee.statut == "terminee",
            )
        )
        if client_id:
            stmt = stmt.where(LivraisonClient.client_id == client_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, livraison_id: int
    ) -> Optional[LivraisonClient]:
        result = await db.execute(
            select(LivraisonClient).where(
                LivraisonClient.id == livraison_id,
                LivraisonClient.livreur_id == livreur_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_ids(
        self, db: AsyncSession, livraison_ids: list[int], livreur_id: int
    ) -> list[LivraisonClient]:
        if not livraison_ids:
            return []
        result = await db.execute(
            select(LivraisonClient).where(
                LivraisonClient.id.in_(livraison_ids),
                LivraisonClient.livreur_id == livreur_id,
            )
        )
        return list(result.scalars().all())

    async def mark_paid(
        self, db: AsyncSession, livraison_ids: list[int], livreur_id: int
    ) -> None:
        for lid in livraison_ids:
            result = await db.execute(
                select(LivraisonClient).where(
                    LivraisonClient.id == lid,
                    LivraisonClient.livreur_id == livreur_id,
                )
            )
            livraison = result.scalar_one_or_none()
            if livraison:
                livraison.is_paid = True
                db.add(livraison)
        await db.commit()


crud_livraison = CRUDLivraisonClient(LivraisonClient)
