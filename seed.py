"""
Script de seed : vide la base et recrée des données de test complètes.
Usage : python3 seed.py  (depuis distripainbe/)
"""
import asyncio
import json
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.admin import Admin
from app.models.acolyte import Acolyte
from app.models.boulangerie import Boulangerie
from app.models.client import Client
from app.models.encaissement import Encaissement
from app.models.livraison_client import LivraisonClient
from app.models.livreur import Livreur
from app.models.portion_pain import PortionPain
from app.models.tournee import Tournee
from app.models.user_session import UserSession
from app.models.zone import Zone
from app.utils.device_detection import detect_device

DATABASE_URL = "sqlite+aiosqlite:///./dev.db"
random.seed(42)


def h(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


def dt(days_ago: int, hour: int = 8) -> datetime:
    base = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return base.replace(hour=hour, minute=0, second=0, microsecond=0)


def d(days_ago: int) -> date:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Base vidée et recréée")

    async with async_session() as db:

        # ── Admin plateforme ────────────────────────────────────────────────
        admin = Admin(
            email="admin@distripain.com",
            password_hash=h("Admin2026!"),
            nom="Super Admin",
        )
        db.add(admin)

        # ── Livreurs ────────────────────────────────────────────────────────
        lv1 = Livreur(
            nom="Amadou Diallo",
            email="amadou@distripain.com",
            password_hash=h("amadou123"),
            telephone="77 100 10 10",
            is_active=True,
            created_at=dt(90),
        )
        lv2 = Livreur(
            nom="Fatou Ndiaye",
            email="fatou@distripain.com",
            password_hash=h("fatou123"),
            telephone="78 200 20 20",
            is_active=True,
            created_at=dt(60),
        )
        lv3 = Livreur(
            nom="Moussa Sow",
            email="moussa@distripain.com",
            password_hash=h("moussa123"),
            telephone="76 300 30 30",
            is_active=False,
            created_at=dt(120),
        )
        db.add_all([lv1, lv2, lv3])
        await db.flush()

        # ── Acolytes ────────────────────────────────────────────────────────
        perms_full = json.dumps([
            "read_clients", "write_clients", "read_boulangeries", "write_boulangeries",
            "read_zones", "write_zones", "read_tournees", "create_tournees",
            "update_tournees", "terminer_tournees", "write_livraisons",
            "read_encaissements", "write_encaissements", "read_stats",
        ])
        perms_livraison = json.dumps([
            "read_clients", "read_tournees", "create_tournees",
            "update_tournees", "terminer_tournees", "write_livraisons",
            "read_encaissements",
        ])

        ac1 = Acolyte(
            nom="Ibrahima Sarr",
            email="ibrahima@distripain.com",
            password_hash=h("ibra456"),
            livreur_principal_id=lv1.id,
            permissions=perms_full,
            is_active=True,
            is_default_password=False,
            created_at=dt(85),
        )
        ac2 = Acolyte(
            nom="Mariama Balde",
            email="mariama@distripain.com",
            password_hash=h("mariama789"),
            livreur_principal_id=lv2.id,
            permissions=perms_livraison,
            is_active=True,
            is_default_password=False,
            created_at=dt(55),
        )
        db.add_all([ac1, ac2])
        await db.flush()

        # ── Boulangeries ────────────────────────────────────────────────────
        bo1 = Boulangerie(livreur_id=lv1.id, nom="Boulangerie Centrale", contact="33 820 10 10", prix_achat_pain=Decimal("40"), is_default=True,  is_active=True)
        bo2 = Boulangerie(livreur_id=lv1.id, nom="Pain Chaud Médina",   contact="33 820 20 20", prix_achat_pain=Decimal("38"), is_default=False, is_active=True)
        bo3 = Boulangerie(livreur_id=lv2.id, nom="Fournil de Thiès",    contact="33 951 00 00", prix_achat_pain=Decimal("40"), is_default=True,  is_active=True)
        db.add_all([bo1, bo2, bo3])
        await db.flush()

        # ── Zones ───────────────────────────────────────────────────────────
        z1 = Zone(livreur_id=lv1.id, nom="Plateau")
        z2 = Zone(livreur_id=lv1.id, nom="Médina")
        z3 = Zone(livreur_id=lv1.id, nom="Grand Dakar")
        z4 = Zone(livreur_id=lv2.id, nom="Centre Thiès")
        z5 = Zone(livreur_id=lv2.id, nom="Zone Résidentielle")
        db.add_all([z1, z2, z3, z4, z5])
        await db.flush()

        # ── Portions de pain ────────────────────────────────────────────────
        db.add_all([
            PortionPain(livreur_id=lv1.id, nom="Petit (50 FCFA)",    prix_fcfa=50,  is_active=True),
            PortionPain(livreur_id=lv1.id, nom="Moyen (75 FCFA)",    prix_fcfa=75,  is_active=True),
            PortionPain(livreur_id=lv1.id, nom="Grand (100 FCFA)",   prix_fcfa=100, is_active=True),
            PortionPain(livreur_id=lv1.id, nom="Familial (150 FCFA)",prix_fcfa=150, is_active=True),
            PortionPain(livreur_id=lv2.id, nom="Standard (75 FCFA)", prix_fcfa=75,  is_active=True),
            PortionPain(livreur_id=lv2.id, nom="Grand (125 FCFA)",   prix_fcfa=125, is_active=True),
        ])

        # ── Clients – Livreur 1 (10 clients) ──────────────────────────────
        noms_lv1 = [
            ("Aliou Gueye",      "77 501 01 01", z1, 75),
            ("Rokhaya Faye",     "77 502 02 02", z1, 100),
            ("Oumar Mbaye",      "77 503 03 03", z1, 75),
            ("Aissatou Diop",    "77 504 04 04", z1, 50),
            ("Babacar Niang",    "77 505 05 05", z2, 100),
            ("Coumba Thiam",     "77 506 06 06", z2, 75),
            ("Pape Sall",        "77 507 07 07", z2, 75),
            ("Ndeye Diallo",     "77 508 08 08", z3, 50),
            ("Seydou Camara",    "77 509 09 09", z3, 100),
            ("Mame Diarra Fall", "77 510 10 10", z3, 75),
        ]
        clients_lv1 = []
        for i, (nom, tel, zone, prix) in enumerate(noms_lv1):
            c = Client(
                livreur_id=lv1.id,
                zone_id=zone.id,
                nom=nom,
                telephone=tel,
                prix_vente_pain=Decimal(str(prix)),
                solde_actuel=Decimal("0"),
                is_active=True,
                created_at=dt(80 - i * 3),
            )
            db.add(c)
            clients_lv1.append(c)

        # ── Clients – Livreur 2 (6 clients) ───────────────────────────────
        noms_lv2 = [
            ("Thierno Ly",       "78 601 01 01", z4, 75),
            ("Khady Sy",         "78 602 02 02", z4, 75),
            ("Abdou Sène",       "78 603 03 03", z4, 75),
            ("Marème Diagne",    "78 604 04 04", z5, 75),
            ("Lamine Diatta",    "78 605 05 05", z5, 75),
            ("Fatoumata Barry",  "78 606 06 06", z5, 75),
        ]
        clients_lv2 = []
        for i, (nom, tel, zone, prix) in enumerate(noms_lv2):
            c = Client(
                livreur_id=lv2.id,
                zone_id=zone.id,
                nom=nom,
                telephone=tel,
                prix_vente_pain=Decimal(str(prix)),
                solde_actuel=Decimal("0"),
                is_active=True,
                created_at=dt(50 - i * 2),
            )
            db.add(c)
            clients_lv2.append(c)

        await db.flush()

        # ── Sessions utilisateur (stats appareils) ──────────────────────────
        ua_android = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0 Mobile Safari/537.36"
        ua_ios     = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Version/16.0 Mobile/15E148 Safari/604.1"
        ua_win     = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/112.0.0.0 Safari/537.36"
        ua_tablet  = "Mozilla/5.0 (Linux; Android 12; SM-T870) AppleWebKit/537.36 Chrome/112.0 Safari/537.36"

        sessions_data = [
            # Amadou – surtout mobile Android
            (lv1.id, ua_android, 45), (lv1.id, ua_android, 38), (lv1.id, ua_android, 30),
            (lv1.id, ua_android, 22), (lv1.id, ua_android, 15), (lv1.id, ua_android, 10),
            (lv1.id, ua_android, 5),  (lv1.id, ua_android, 2),  (lv1.id, ua_android, 1),
            (lv1.id, ua_win, 40),     (lv1.id, ua_tablet, 20),  (lv1.id, ua_tablet, 12),
            # Fatou – mobile iOS
            (lv2.id, ua_ios, 50), (lv2.id, ua_ios, 40), (lv2.id, ua_ios, 30),
            (lv2.id, ua_ios, 20), (lv2.id, ua_ios, 10), (lv2.id, ua_ios, 5),
            (lv2.id, ua_ios, 2),  (lv2.id, ua_win, 45), (lv2.id, ua_android, 25),
            # Moussa – desktop uniquement
            (lv3.id, ua_win, 100), (lv3.id, ua_win, 90),
        ]
        for livreur_id, ua, days_ago in sessions_data:
            device_type, platform, browser = detect_device(ua)
            db.add(UserSession(
                livreur_id=livreur_id,
                device_type=device_type,
                platform=platform,
                browser=browser,
                user_agent=ua[:512],
                logged_in_at=dt(days_ago),
            ))

        await db.flush()

        # ── Tournées + Livraisons + Encaissements ──────────────────────────
        async def make_tournee(livreur, boulangerie, day_ago, periode, clients_subset, statut="terminee"):
            nb_pris = random.randint(50, 130)
            t = Tournee(
                livreur_id=livreur.id,
                boulangerie_id=boulangerie.id,
                date=d(day_ago),
                periode=periode,
                nb_pains_pris=nb_pris,
                nb_pains_ecoules=0,
                nb_pains_retournes=0,
                statut=statut,
                created_at=dt(day_ago, 6 if periode == "matin" else 16),
            )
            db.add(t)
            await db.flush()

            total_ecoules = 0
            livraisons = []
            for client in clients_subset:
                nb_livres   = random.randint(2, 12)
                nb_retournes = random.randint(0, 1)
                net = max(0, nb_livres - nb_retournes)
                total_ecoules += net
                prix = client.prix_vente_pain or Decimal("75")
                montant = prix * net
                lv_obj = LivraisonClient(
                    tournee_id=t.id,
                    client_id=client.id,
                    livreur_id=livreur.id,
                    nb_pains_livres=nb_livres,
                    nb_pains_retournes=nb_retournes,
                    prix_unitaire=prix,
                    montant_du=montant,
                    is_termine=(statut == "terminee"),
                )
                db.add(lv_obj)
                livraisons.append((client, montant))

            if statut == "terminee":
                t.nb_pains_ecoules  = total_ecoules
                t.nb_pains_retournes = max(0, nb_pris - total_ecoules)
                db.add(t)

            await db.flush()

            # Encaissements pour les tournées terminées
            if statut == "terminee":
                for client, montant in livraisons:
                    if montant <= 0:
                        continue
                    roll = random.random()
                    if roll < 0.55:          # 55% paiement complet
                        enc_type, enc_montant = "complet", montant
                    elif roll < 0.72:        # 17% partiel
                        enc_type, enc_montant = "partiel", montant / 2
                    elif roll < 0.82:        # 10% dette
                        enc_type, enc_montant = "dette", Decimal("0")
                    else:                    # 18% pas d'encaissement (crédit ouvert)
                        continue
                    db.add(Encaissement(
                        livreur_id=livreur.id,
                        client_id=client.id,
                        montant=enc_montant,
                        type=enc_type,
                        livraisons_soldees="[]",
                        date_encaissement=dt(day_ago, 11),
                        created_at=dt(day_ago, 11),
                    ))

        # Livreur 1 : 30 tournées terminées (2 par jour sur 60 jours, un sur deux)
        for day in range(1, 61, 2):
            subset = random.sample(clients_lv1, k=random.randint(5, 9))
            boul   = bo1 if day % 3 != 0 else bo2
            await make_tournee(lv1, boul, day, "matin", subset, "terminee")
            # certains jours aussi une tournée soir
            if day % 4 == 1:
                subset2 = random.sample(clients_lv1, k=random.randint(3, 6))
                await make_tournee(lv1, boul, day, "soir", subset2, "terminee")

        # Livreur 1 : tournée en cours aujourd'hui (matin)
        t_ec1 = Tournee(
            livreur_id=lv1.id, boulangerie_id=bo1.id,
            date=d(0), periode="matin",
            nb_pains_pris=90, nb_pains_ecoules=0, nb_pains_retournes=0,
            statut="en_cours", created_at=dt(0, 6),
        )
        db.add(t_ec1)
        await db.flush()
        for client in clients_lv1[:6]:
            nb = random.randint(3, 9)
            prix = client.prix_vente_pain or Decimal("75")
            db.add(LivraisonClient(
                tournee_id=t_ec1.id, client_id=client.id, livreur_id=lv1.id,
                nb_pains_livres=nb, nb_pains_retournes=0,
                prix_unitaire=prix, montant_du=prix * nb, is_termine=False,
            ))

        # Livreur 2 : 22 tournées terminées
        for day in range(1, 45, 2):
            subset = random.sample(clients_lv2, k=random.randint(3, 6))
            await make_tournee(lv2, bo3, day, "matin" if day % 2 == 0 else "soir", subset, "terminee")

        # Livreur 2 : tournée en cours aujourd'hui (soir)
        t_ec2 = Tournee(
            livreur_id=lv2.id, boulangerie_id=bo3.id,
            date=d(0), periode="soir",
            nb_pains_pris=60, nb_pains_ecoules=0, nb_pains_retournes=0,
            statut="en_cours", created_at=dt(0, 16),
        )
        db.add(t_ec2)
        await db.flush()
        for client in clients_lv2[:4]:
            nb = random.randint(2, 7)
            db.add(LivraisonClient(
                tournee_id=t_ec2.id, client_id=client.id, livreur_id=lv2.id,
                nb_pains_livres=nb, nb_pains_retournes=0,
                prix_unitaire=Decimal("75"), montant_du=Decimal("75") * nb,
                is_termine=False,
            ))

        await db.commit()

    print("\n✅ Seed terminé avec succès !")
    print("   3 livreurs | 2 acolytes | 1 admin plateforme")
    print("   16 clients | 3 boulangeries | 5 zones | 6 portions")
    print("   ~52 tournées terminées + 2 en cours | ~300 livraisons")
    print("   23 sessions utilisateur (Android/iOS/Desktop/Tablet)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
