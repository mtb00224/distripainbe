from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LivreurInterne(Base):
    """
    Agent de livraison créé par une boulangerie.
    Pas forcément un utilisateur du système — juste un nom + téléphone.
    Si un jour il s'inscrit avec le même numéro de téléphone,
    son user_id est automatiquement rattaché.
    """
    __tablename__ = "livreurs_internes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boulangerie_id: Mapped[int] = mapped_column(
        ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=False, index=True
    )

    prenom: Mapped[str] = mapped_column(String(50), nullable=False)
    nom: Mapped[str] = mapped_column(String(50), nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    # Prix auquel la boulangerie lui cède le pain par défaut
    prix_achat_pain: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Rattaché automatiquement si ce livreur crée un compte avec le même téléphone
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relations
    boulangerie: Mapped["Boulangerie"] = relationship("Boulangerie", back_populates="livreurs_internes")
    user: Mapped["User | None"] = relationship("User")
    distributions: Mapped[list["DistributionLivreur"]] = relationship(
        "DistributionLivreur", back_populates="livreur_interne", cascade="all, delete-orphan"
    )
    compte_interne: Mapped["CompteInterneLivreur | None"] = relationship(
        "CompteInterneLivreur", back_populates="livreur_interne",
        uselist=False, cascade="all, delete-orphan"
    )
    portions: Mapped[list["LivreurInternePortionPain"]] = relationship(
        "LivreurInternePortionPain", back_populates="livreur_interne",
        cascade="all, delete-orphan", order_by="LivreurInternePortionPain.nom"
    )

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}".strip()


class CompteInterneLivreur(Base):
    """
    Compte courant interne d'un livreur au sein de la boulangerie.
    Le livreur peut choisir de laisser ses gains et les retirer en fin de mois.
    """
    __tablename__ = "comptes_internes_livreur"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_interne_id: Mapped[int] = mapped_column(
        ForeignKey("livreurs_internes.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    solde_actuel: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relations
    livreur_interne: Mapped["LivreurInterne"] = relationship(
        "LivreurInterne", back_populates="compte_interne"
    )
    retraits: Mapped[list["RetirementCompte"]] = relationship(
        "RetirementCompte", back_populates="compte", cascade="all, delete-orphan"
    )


class RetirementCompte(Base):
    """Retrait du solde du compte interne d'un livreur."""
    __tablename__ = "retraits_compte_interne"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    compte_id: Mapped[int] = mapped_column(
        ForeignKey("comptes_internes_livreur.id", ondelete="CASCADE"), nullable=False, index=True
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date_retrait: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relations
    compte: Mapped["CompteInterneLivreur"] = relationship(
        "CompteInterneLivreur", back_populates="retraits"
    )
    created_by: Mapped["User"] = relationship("User")
