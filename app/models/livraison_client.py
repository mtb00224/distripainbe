from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LivraisonClient(Base):
    __tablename__ = "livraisons_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nb_pains_livres: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nb_pains_retournes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    montant_du: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_termine: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tournee: Mapped["Tournee"] = relationship("Tournee", back_populates="livraisons")  # noqa: F821
    client: Mapped["Client"] = relationship("Client", back_populates="livraisons")  # noqa: F821
