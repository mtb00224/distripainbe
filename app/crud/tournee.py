from datetime import date
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.retour_pain import RetourPain
from app.models.tournee import Tournee


def _tournee_options():
    return [
        selectinload(Tournee.boulangerie),
        selectinload(Tournee.retour_lignes).selectinload(RetourPain.portion),
    ]


class CRUDTournee(CRUDBase[Tournee]):
    async def get_by_livreur(
        self,
        db: AsyncSession,
        livreur_id: int,
        date_filter: Optional[date] = None,
        periode: Optional[str] = None,
        boulangerie_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Tournee]:
        stmt = (
            select(Tournee)
            .options(*_tournee_options())
            .where(Tournee.livreur_id == livreur_id)
        )
        if date_filter:
            stmt = stmt.where(Tournee.date == date_filter)
        if periode:
            stmt = stmt.where(Tournee.periode == periode)
        if boulangerie_id:
            stmt = stmt.where(Tournee.boulangerie_id == boulangerie_id)
        stmt = stmt.order_by(Tournee.date.desc(), Tournee.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, tournee_id: int
    ) -> Optional[Tournee]:
        result = await db.execute(
            select(Tournee)
            .options(*_tournee_options())
            .where(Tournee.id == tournee_id, Tournee.livreur_id == livreur_id)
        )
        return result.scalar_one_or_none()


crud_tournee = CRUDTournee(Tournee)
