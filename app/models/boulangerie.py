import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StaffRole(str, enum.Enum):
    GERANT = "gerant"
    COMPTABLE = "comptable"
    VENDEUR = "vendeur"


class Boulangerie(Base):
    __tablename__ = "boulangeries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prix_vente_pain: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Le patron qui possède cette boulangerie (nullable si créée par un livreur comme fournisseur)
    admin_boulangerie_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_boulangeries.id", ondelete="SET NULL"), nullable=True
    )
    admin_boulangerie: Mapped["AdminBoulangerie | None"] = relationship(
        "AdminBoulangerie", back_populates="boulangeries"
    )

    # Membres du personnel
    staff_members: Mapped[list["StaffBoulangerie"]] = relationship(
        "StaffBoulangerie", back_populates="boulangerie", cascade="all, delete-orphan"
    )

    # Livreurs liés (via table de contrat)
    livreurs_links: Mapped[list["LivreurBoulangerie"]] = relationship(
        "LivreurBoulangerie", back_populates="boulangerie", cascade="all, delete-orphan"
    )

    # Tournées (livreurs indépendants)
    tournees: Mapped[list["Tournee"]] = relationship(
        "Tournee", back_populates="boulangerie"
    )

    # Sessions de production (côté boulangerie)
    sessions_production: Mapped[list["SessionProduction"]] = relationship(
        "SessionProduction", back_populates="boulangerie", cascade="all, delete-orphan"
    )

    # Livreurs internes
    livreurs_internes: Mapped[list["LivreurInterne"]] = relationship(
        "LivreurInterne", back_populates="boulangerie", cascade="all, delete-orphan"
    )

    # Dépenses
    depenses: Mapped[list["Depense"]] = relationship(
        "Depense", back_populates="boulangerie", cascade="all, delete-orphan"
    )

    # Produits ambulatoires
    produits_ambulatoires: Mapped[list["ProduitAmbulateur"]] = relationship(
        "ProduitAmbulateur", back_populates="boulangerie", cascade="all, delete-orphan"
    )


class AdminBoulangerie(Base):
    """Propriétaire d'une ou plusieurs boulangeries."""
    __tablename__ = "admin_boulangeries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    user: Mapped["User"] = relationship("User", back_populates="admin_boulangerie_profile")
    boulangeries: Mapped[list["Boulangerie"]] = relationship(
        "Boulangerie", back_populates="admin_boulangerie"
    )
    portions_pain: Mapped[list["PortionPainBoulangerie"]] = relationship(
        "PortionPainBoulangerie", back_populates="admin_boulangerie", cascade="all, delete-orphan",
        order_by="PortionPainBoulangerie.ordre",
    )

    # Propriétés pratiques
    @property
    def first_name(self) -> str:
        return self.user.first_name if self.user else ""

    @property
    def last_name(self) -> str:
        return self.user.last_name if self.user else ""

    @property
    def email(self) -> str | None:
        return self.user.email if self.user else None


class StaffBoulangerie(Base):
    __tablename__ = "staff_boulangeries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    boulangerie_id: Mapped[int] = mapped_column(
        ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=False
    )
    role_interne: Mapped[StaffRole] = mapped_column(SAEnum(StaffRole), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(
        "User", back_populates="staff_positions", foreign_keys=[user_id]
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    boulangerie: Mapped["Boulangerie"] = relationship("Boulangerie", back_populates="staff_members")

    @property
    def first_name(self) -> str:
        return self.user.first_name if self.user else ""

    @property
    def last_name(self) -> str:
        return self.user.last_name if self.user else ""

    @property
    def email(self) -> str | None:
        return self.user.email if self.user else None


# =====================
# Dépenses
# =====================

class CategorieDepense(Base):
    __tablename__ = "categorie_depenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    depenses: Mapped[list["Depense"]] = relationship("Depense", back_populates="categorie")


class Depense(Base):
    __tablename__ = "depenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boulangerie_id: Mapped[int] = mapped_column(ForeignKey("boulangeries.id"), nullable=False)
    categorie_id: Mapped[int] = mapped_column(ForeignKey("categorie_depenses.id"), nullable=False)
    motif: Mapped[str] = mapped_column(String(255), nullable=False)
    quantite: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=1)
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date_enregistrement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    @property
    def montant_total(self) -> Decimal:
        return self.quantite * self.prix_unitaire

    boulangerie: Mapped["Boulangerie"] = relationship("Boulangerie", back_populates="depenses")
    categorie: Mapped["CategorieDepense"] = relationship("CategorieDepense", back_populates="depenses")
    created_by: Mapped["User"] = relationship("User")


# =====================
# Portions de pain (config par admin boulangerie)
# =====================

class PortionPainBoulangerie(Base):
    """
    Configuration des portions de pain pour un admin boulangerie.
    Commune à toutes ses boulangeries.
    Exemple : Pain entier (1.0), Demi-pain (0.5), Quart (0.25).
    Utilisée pour le comptage des retours des livreurs internes.
    """
    __tablename__ = "portions_pain_boulangerie"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_boulangerie_id: Mapped[int] = mapped_column(
        ForeignKey("admin_boulangeries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(50), nullable=False)
    equivalent_pains: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    admin_boulangerie: Mapped["AdminBoulangerie"] = relationship(
        "AdminBoulangerie", back_populates="portions_pain"
    )
