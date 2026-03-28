"""
Bilan service — calculates client balances and payment statuses.
"""
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.livraison_client import LivraisonClient
from app.models.encaissement import Encaissement
from app.models.dette import ReglementDette
from app.models.client import Client


def get_payment_status(solde: Decimal) -> str:
    if solde <= 0:
        return "solde"
    return "impaye"


async def recalculate_client_solde(db: AsyncSession, client_id: int) -> Decimal:
    """
    solde = sum(all livraisons montant_du) - sum(all encaissements montant)
    Positive = client owes money. Negative = client has credit.
    Handles partial payments correctly.
    """
    r1 = await db.execute(
        select(func.sum(LivraisonClient.montant_du)).where(
            LivraisonClient.client_id == client_id,
        )
    )
    total_livraisons = r1.scalar_one() or Decimal("0")

    r2 = await db.execute(
        select(func.sum(Encaissement.montant)).where(
            Encaissement.client_id == client_id,
            Encaissement.type != "dette",  # Les dettes ne réduisent pas le solde tant qu'elles ne sont pas réglées
        )
    )
    total_encaisse = r2.scalar_one() or Decimal("0")

    # Ajouter les réglements de dettes (paiements effectués sur les dettes)
    from app.models.dette import Dette
    r3_sub = select(Dette.id).where(Dette.client_id == client_id)
    r3 = await db.execute(
        select(func.sum(ReglementDette.montant)).where(
            ReglementDette.dette_id.in_(r3_sub)
        )
    )
    total_reglements = r3.scalar_one() or Decimal("0")

    solde = total_livraisons - total_encaisse - total_reglements

    r3 = await db.execute(select(Client).where(Client.id == client_id))
    client = r3.scalar_one_or_none()
    if client:
        client.solde_actuel = solde
        db.add(client)
        await db.commit()

    return solde


async def get_client_historique(
    db: AsyncSession, livreur_id: int, client_id: int
) -> dict:
    from sqlalchemy.orm import selectinload
    from app.models.client import Client as ClientModel

    livraisons_result = await db.execute(
        select(LivraisonClient).where(
            LivraisonClient.client_id == client_id,
            LivraisonClient.livreur_id == livreur_id,
        ).order_by(LivraisonClient.created_at.desc())
    )
    livraisons = list(livraisons_result.scalars().all())

    encaissements_result = await db.execute(
        select(Encaissement).where(
            Encaissement.client_id == client_id,
            Encaissement.livreur_id == livreur_id,
        ).order_by(Encaissement.date_encaissement.desc())
    )
    encaissements = list(encaissements_result.scalars().all())

    total_livraisons = sum(l.montant_du for l in livraisons)
    total_encaisse = sum(e.montant for e in encaissements)

    return {
        "total_livraisons": len(livraisons),
        "total_encaisse": float(total_encaisse),
        "solde": float(total_livraisons - total_encaisse),
        "livraisons": [
            {
                "id": l.id,
                "created_at": l.created_at.isoformat(),
                "nb_pains_livres": l.nb_pains_livres,
                "nb_pains_retournes": l.nb_pains_retournes,
                "montant_du": float(l.montant_du),
                "is_paid": l.is_paid,
            }
            for l in livraisons
        ],
        "encaissements": [
            {
                "id": e.id,
                "date_encaissement": e.date_encaissement.isoformat(),
                "montant": float(e.montant),
                "type": e.type,
            }
            for e in encaissements
        ],
    }
