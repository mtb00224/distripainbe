from datetime import datetime, timezone
from decimal import Decimal
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DetteBoulangerieType(str, enum.Enum):
    LIVREUR_DOIT = "livreur_doit"       # Le livreur doit de l'argent à la boulangerie
    BOULANGERIE_DOIT = "boulangerie_doit"  # La boulangerie doit de l'argent au livreur


class DetteBoulangerieStatut(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    PARTIELLEMENT_REGLE = "partiellement_regle"
    REGLE = "regle"
    ANNULE = "annule"


class DetteBoulangerie(Base):
    """Dette entre la boulangerie et un livreur interne."""
    __tablename__ = "dettes_boulangerie"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    boulangerie_id: Mapped[int] = mapped_column(
        ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    livreur_interne_id: Mapped[int] = mapped_column(
        ForeignKey("livreurs_internes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    type: Mapped[DetteBoulangerieType] = mapped_column(
        Enum(DetteBoulangerieType), nullable=False
    )
    motif: Mapped[str] = mapped_column(String(255), nullable=False)
    montant_initial: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    montant_restant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    statut: Mapped[DetteBoulangerieStatut] = mapped_column(
        Enum(DetteBoulangerieStatut),
        nullable=False,
        default=DetteBoulangerieStatut.EN_ATTENTE,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    # Relations
    livreur_interne: Mapped["LivreurInterne"] = relationship("LivreurInterne")
    reglements: Mapped[list["ReglementDetteBoulangerie"]] = relationship(
        "ReglementDetteBoulangerie",
        back_populates="dette",
        cascade="all, delete-orphan",
        order_by="ReglementDetteBoulangerie.created_at",
    )


class ReglementDetteBoulangerie(Base):
    """Versement partiel ou total pour solder une dette boulangerie."""
    __tablename__ = "reglements_dette_boulangerie"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dette_id: Mapped[int] = mapped_column(
        ForeignKey("dettes_boulangerie.id", ondelete="CASCADE"), nullable=False, index=True
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    # Relations
    dette: Mapped["DetteBoulangerie"] = relationship("DetteBoulangerie", back_populates="reglements")
