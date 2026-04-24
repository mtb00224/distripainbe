from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class LivraisonClient(Base):
    __tablename__ = "livraisons_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Lien vers la tournée (obligatoire pour le suivi logistique)
    tournee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Identification du propriétaire de la livraison
    livreur_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    boulangerie_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Détails de la dépose
    nb_pains_livres: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nb_pains_retournes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Prix appliqué à ce moment précis (peut varier selon le client)
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Montant dû calculé et stocké (nb_pains_livres - nb_pains_retournes) * prix_unitaire
    montant_du: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    # États de paiement
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # is_termine peut servir à "verrouiller" la livraison pour qu'on ne puisse plus la modifier
    is_termine: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Traçabilité
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tournee: Mapped["Tournee"] = relationship("Tournee", back_populates="livraisons")
    client: Mapped["Client"] = relationship("Client", back_populates="livraisons")
    user: Mapped["User"] = relationship("User")
