from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.livreur import Livreur
from app.models.user import User, UserRole
from app.core.security import hash_password


class CRUDLivreur(CRUDBase[Livreur]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[Livreur]:
        result = await db.execute(
            select(Livreur)
            .join(User, Livreur.user_id == User.id)
            .options(selectinload(Livreur.user))
            .where(User.email == email, User.role == UserRole.LIVREUR)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[Livreur]:
        result = await db.execute(
            select(Livreur)
            .join(User, Livreur.user_id == User.id)
            .options(selectinload(Livreur.user))
            .where(User.username == username, User.role == UserRole.LIVREUR)
        )
        return result.scalar_one_or_none()

    async def get_with_user(self, db: AsyncSession, livreur_id: int) -> Optional[Livreur]:
        result = await db.execute(
            select(Livreur)
            .options(selectinload(Livreur.user))
            .where(Livreur.id == livreur_id)
        )
        return result.scalar_one_or_none()

    async def create_livreur(
        self,
        db: AsyncSession,
        *,
        first_name: str,
        last_name: str,
        username: str,
        email: str,
        password: str,
        phone_number: Optional[str] = None,
    ) -> Livreur:
        user = User(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            phone_number=phone_number or "",
            role=UserRole.LIVREUR,
            password_hash=hash_password(password),
        )
        db.add(user)
        await db.flush()

        livreur = Livreur(user_id=user.id)
        db.add(livreur)
        await db.commit()

        result = await db.execute(
            select(Livreur)
            .options(selectinload(Livreur.user))
            .where(Livreur.id == livreur.id)
        )
        return result.scalar_one()


crud_livreur = CRUDLivreur(Livreur)
