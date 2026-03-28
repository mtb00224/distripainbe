from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    pays_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pays.id", ondelete="SET NULL"), nullable=True
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prix_vente_pain: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    solde_actuel: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    livreur: Mapped["Livreur"] = relationship("Livreur", back_populates="clients")  # noqa: F821
    zone: Mapped["Zone | None"] = relationship("Zone", back_populates="clients")  # noqa: F821
    pays: Mapped["Pays | None"] = relationship("Pays", back_populates="clients")  # noqa: F821
    livraisons: Mapped[list["LivraisonClient"]] = relationship(  # noqa: F821
        "LivraisonClient", back_populates="client", cascade="all, delete-orphan"
    )
    encaissements: Mapped[list["Encaissement"]] = relationship(  # noqa: F821
        "Encaissement", back_populates="client"
    )
