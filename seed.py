"""
Seed minimal — vide la base et crée des comptes de test propres.
Usage : python3 seed.py  (depuis distripainbe/)
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import bcrypt

from app.db.base import Base
from app.models.user import User, UserRole
from app.models.livreur import Livreur, AcolyteLivreur
from app.models.boulangerie import AdminBoulangerie, Boulangerie, CategorieDepense

DATABASE_URL = "sqlite+aiosqlite:///./dev.db"


def h(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Base vidée et recréée")

    async with async_session() as db:

        # ── Catégories de dépenses (globales) ──────────────────────────────
        for nom, desc in [
            ("Matière première", "Farine, sel, levure, etc."),
            ("Salaires", "Rémunération du personnel"),
            ("Énergie", "Électricité, gaz, bois de chauffe"),
            ("Équipement", "Achat ou réparation de matériel"),
            ("Loyer", "Loyer des locaux"),
            ("Transport", "Carburant, livraisons fournisseurs"),
            ("Autre", "Autres dépenses diverses"),
        ]:
            db.add(CategorieDepense(nom=nom, description=desc))

        # ── Admin plateforme ────────────────────────────────────────────────
        admin_user = User(
            first_name="Super",
            last_name="Admin",
            username="superadmin",
            email="admin@distripain.com",
            phone_number="",
            role=UserRole.ADMIN,
            password_hash=h("Admin2026!"),
        )
        db.add(admin_user)

        # ── Livreur test ────────────────────────────────────────────────────
        livreur_user = User(
            first_name="Amadou",
            last_name="Diallo",
            username="amadou.diallo",
            email="amadou@distripain.com",
            phone_number="77 100 10 10",
            role=UserRole.LIVREUR,
            password_hash=h("Livreur2026!"),
        )
        db.add(livreur_user)
        await db.flush()

        livreur = Livreur(user_id=livreur_user.id)
        db.add(livreur)
        await db.flush()

        # ── Admin boulangerie test ──────────────────────────────────────────
        ab_user = User(
            first_name="Fatou",
            last_name="Ndiaye",
            username="fatou.ndiaye",
            email="fatou@distripain.com",
            phone_number="78 200 20 20",
            role=UserRole.ADMIN_BOULANGERIE,
            password_hash=h("Boulangerie2026!"),
        )
        db.add(ab_user)
        await db.flush()

        admin_b = AdminBoulangerie(user_id=ab_user.id)
        db.add(admin_b)
        await db.flush()

        boulangerie = Boulangerie(
            nom="Boulangerie Centrale",
            contact="33 820 10 10",
            admin_boulangerie_id=admin_b.id,
        )
        db.add(boulangerie)

        await db.commit()

    print("\n✅ Seed terminé !")
    print("   Comptes créés :")
    print("   ├── Admin plateforme  : admin@distripain.com      / Admin2026!")
    print("   ├── Livreur           : amadou@distripain.com     / Livreur2026!")
    print("   └── Admin boulangerie : fatou@distripain.com      / Boulangerie2026!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
