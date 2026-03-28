from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.livreur import Livreur
from app.core.security import hash_password


class CRUDLivreur(CRUDBase[Livreur]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[Livreur]:
        result = await db.execute(select(Livreur).where(Livreur.email == email))
        return result.scalar_one_or_none()

    async def create_livreur(self, db: AsyncSession, *, nom: str, email: str, password: str, telephone: Optional[str] = None) -> Livreur:
        livreur = Livreur(
            nom=nom,
            email=email,
            password_hash=hash_password(password),
            telephone=telephone,
        )
        db.add(livreur)
        await db.commit()
        await db.refresh(livreur)
        return livreur


crud_livreur = CRUDLivreur(Livreur)
