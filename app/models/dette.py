from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Dette(Base):
    """Debt record — created automatically from 'dette' or 'partiel' encaissements, or manually."""
    __tablename__ = "dettes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # encaissement that triggered this debt (nullable for manual debts)
    encaissement_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("encaissements.id", ondelete="SET NULL"), nullable=True
    )
    # JSON list of livraison_client IDs concerned by this debt
    livraison_ids: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    montant_initial: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    montant_restant: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # 'en_cours', 'soldee_partiellement', 'soldee_totalement'
    statut: Mapped[str] = mapped_column(String(30), nullable=False, default="en_cours")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    reglements: Mapped[list["ReglementDette"]] = relationship(
        "ReglementDette", back_populates="dette", cascade="all, delete-orphan"
    )
    client: Mapped["Client"] = relationship("Client")  # noqa: F821


class ReglementDette(Base):
    """A single payment applied against a debt (full or partial)."""
    __tablename__ = "reglements_dette"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dette_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dettes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    date_reglement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    dette: Mapped["Dette"] = relationship("Dette", back_populates="reglements")
