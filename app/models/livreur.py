from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LivreurBoulangerie(Base):
    """Table de contrat : prix négociés par livreur et par boulangerie."""
    __tablename__ = "livreur_boulangeries"

    livreur_id: Mapped[int] = mapped_column(
        ForeignKey("livreurs.id", ondelete="CASCADE"), primary_key=True
    )
    boulangerie_id: Mapped[int] = mapped_column(
        ForeignKey("boulangeries.id", ondelete="CASCADE"), primary_key=True
    )
    prix_achat_pain: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    contact_local: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    livreur: Mapped["Livreur"] = relationship("Livreur", back_populates="boulangeries_links")
    boulangerie: Mapped["Boulangerie"] = relationship(
        "Boulangerie", back_populates="livreurs_links"
    )


class Livreur(Base):
    __tablename__ = "livreurs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Compte utilisateur lié
    user: Mapped["User"] = relationship("User", back_populates="livreur_profile")

    # Boulangeries liées (contrats)
    boulangeries_links: Mapped[list["LivreurBoulangerie"]] = relationship(
        "LivreurBoulangerie", back_populates="livreur", cascade="all, delete-orphan"
    )

    # Acolytes
    acolytes: Mapped[list["AcolyteLivreur"]] = relationship(
        "AcolyteLivreur", back_populates="livreur_principal", cascade="all, delete-orphan"
    )

    # Relations métier
    zones: Mapped[list["Zone"]] = relationship(
        "Zone", back_populates="livreur", cascade="all, delete-orphan"
    )
    tournees: Mapped[list["Tournee"]] = relationship(
        "Tournee", back_populates="livreur", cascade="all, delete-orphan"
    )
    encaissements: Mapped[list["Encaissement"]] = relationship(
        "Encaissement", back_populates="livreur", cascade="all, delete-orphan"
    )
    portions: Mapped[list["PortionPain"]] = relationship(
        "PortionPain", back_populates="livreur", cascade="all, delete-orphan"
    )
    abonnements: Mapped[list["Abonnement"]] = relationship(
        "Abonnement", back_populates="livreur", cascade="all, delete-orphan"
    )
    clients: Mapped[list["Client"]] = relationship(
        "Client", back_populates="livreur", cascade="all, delete-orphan"
    )

    # =====================
    # Propriétés pratiques (délèguent à User)
    # =====================
    @property
    def first_name(self) -> str:
        return self.user.first_name if self.user else ""

    @property
    def last_name(self) -> str:
        return self.user.last_name if self.user else ""

    @property
    def nom(self) -> str:
        """Nom complet — rétrocompatibilité."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def username(self) -> str:
        return self.user.username if self.user else ""

    @property
    def phone_number(self) -> str:
        return self.user.phone_number if self.user else ""

    @property
    def is_active(self) -> bool:
        return self.user.is_active if self.user else False


class AcolyteLivreur(Base):
    __tablename__ = "acolytes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    livreur_principal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False
    )
    permissions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    livreur_principal: Mapped["Livreur"] = relationship("Livreur", back_populates="acolytes")

    # =====================
    # Propriétés pratiques
    # =====================
    @property
    def first_name(self) -> str:
        return self.user.first_name if self.user else ""

    @property
    def last_name(self) -> str:
        return self.user.last_name if self.user else ""

    @property
    def nom(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def username(self) -> str:
        return self.user.username if self.user else ""

    @property
    def password_hash(self) -> str:
        return self.user.password_hash if self.user else ""

    @property
    def is_default_password(self) -> bool:
        return self.user.must_change_password if self.user else False
