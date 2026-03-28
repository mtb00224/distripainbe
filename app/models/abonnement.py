from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FormulaAbonnement(Base):
    __tablename__ = "formules_abonnement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # pays_id null = formule globale visible par tous les livreurs
    pays_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pays.id", ondelete="SET NULL"), nullable=True
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    duree_mois: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 3, 12
    prix: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    pays: Mapped["Pays | None"] = relationship("Pays")  # noqa: F821
    abonnements: Mapped[list["Abonnement"]] = relationship(
        "Abonnement", back_populates="formule"
    )


class Abonnement(Base):
    __tablename__ = "abonnements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    formule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("formules_abonnement.id"), nullable=False
    )
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date] = mapped_column(Date, nullable=False)
    # en_attente | actif | expire | suspendu
    statut: Mapped[str] = mapped_column(String(20), default="en_attente", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    livreur: Mapped["Livreur"] = relationship(  # noqa: F821
        "Livreur", back_populates="abonnements"
    )
    formule: Mapped["FormulaAbonnement"] = relationship(
        "FormulaAbonnement", back_populates="abonnements"
    )
    paiements: Mapped[list["PaiementAbonnement"]] = relationship(
        "PaiementAbonnement", back_populates="abonnement", cascade="all, delete-orphan"
    )


class PaiementAbonnement(Base):
    __tablename__ = "paiements_abonnement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    abonnement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("abonnements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    moyen: Mapped[str] = mapped_column(String(50), nullable=False)    # Wave, Orange Money…
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # en_attente | valide | rejete
    statut: Mapped[str] = mapped_column(String(20), default="en_attente", nullable=False)
    notes_admin: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_paiement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    date_validation: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    abonnement: Mapped["Abonnement"] = relationship("Abonnement", back_populates="paiements")
    livreur: Mapped["Livreur"] = relationship("Livreur")  # noqa: F821
