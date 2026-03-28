from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Encaissement(Base):
    __tablename__ = "encaissements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_acolyte_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("acolytes.id", ondelete="SET NULL"), nullable=True
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    date_encaissement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # JSON list of livraison_client IDs e.g. '[1, 2, 3]'
    livraisons_soldees: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # 'complet', 'partiel', 'avance', 'dette'
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    livreur: Mapped["Livreur"] = relationship("Livreur", back_populates="encaissements")  # noqa: F821
    client: Mapped["Client"] = relationship("Client", back_populates="encaissements")  # noqa: F821
