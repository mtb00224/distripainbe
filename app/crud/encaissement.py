import json
from typing import Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.encaissement import Encaissement
from app.models.client import Client


class CRUDEncaissement(CRUDBase[Encaissement]):
    async def get_by_livreur(
        self,
        db: AsyncSession,
        livreur_id: int,
        client_id: Optional[int] = None,
        date_debut: Optional[datetime] = None,
        date_fin: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Encaissement]:
        stmt = (
            select(Encaissement)
            .options(selectinload(Encaissement.client).selectinload(Client.zone))
            .where(Encaissement.livreur_id == livreur_id)
        )
        if client_id:
            stmt = stmt.where(Encaissement.client_id == client_id)
        if date_debut:
            stmt = stmt.where(Encaissement.date_encaissement >= date_debut)
        if date_fin:
            stmt = stmt.where(Encaissement.date_encaissement <= date_fin)
        stmt = stmt.order_by(Encaissement.date_encaissement.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_livreur_and_id(
        self, db: AsyncSession, livreur_id: int, encaissement_id: int
    ) -> Optional[Encaissement]:
        result = await db.execute(
            select(Encaissement)
            .options(selectinload(Encaissement.client).selectinload(Client.zone))
            .where(
                Encaissement.id == encaissement_id,
                Encaissement.livreur_id == livreur_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_encaissement(
        self,
        db: AsyncSession,
        *,
        livreur_id: int,
        client_id: int,
        montant,
        livraisons_soldees: list[int],
        type_enc: str,
        notes: Optional[str],
        date_encaissement: Optional[datetime],
        acolyte_id: Optional[int],
    ) -> Encaissement:
        from datetime import timezone
        enc = Encaissement(
            livreur_id=livreur_id,
            client_id=client_id,
            montant=montant,
            livraisons_soldees=json.dumps(livraisons_soldees),
            type=type_enc,
            notes=notes,
            date_encaissement=date_encaissement or datetime.now(timezone.utc),
            created_by_acolyte_id=acolyte_id,
        )
        db.add(enc)
        await db.commit()
        await db.refresh(enc)
        return enc


crud_encaissement = CRUDEncaissement(Encaissement)
