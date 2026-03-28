from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Livreur(Base):
    __tablename__ = "livreurs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pays_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pays.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # JSON list of allowed permissions — null means all permissions granted (default)
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    pays: Mapped["Pays | None"] = relationship("Pays")  # noqa: F821

    acolytes: Mapped[list["Acolyte"]] = relationship(  # noqa: F821
        "Acolyte", back_populates="livreur_principal", cascade="all, delete-orphan"
    )
    boulangeries: Mapped[list["Boulangerie"]] = relationship(  # noqa: F821
        "Boulangerie", back_populates="livreur", cascade="all, delete-orphan"
    )
    zones: Mapped[list["Zone"]] = relationship(  # noqa: F821
        "Zone", back_populates="livreur", cascade="all, delete-orphan"
    )
    clients: Mapped[list["Client"]] = relationship(  # noqa: F821
        "Client", back_populates="livreur", cascade="all, delete-orphan"
    )
    tournees: Mapped[list["Tournee"]] = relationship(  # noqa: F821
        "Tournee", back_populates="livreur", cascade="all, delete-orphan"
    )
    encaissements: Mapped[list["Encaissement"]] = relationship(  # noqa: F821
        "Encaissement", back_populates="livreur", cascade="all, delete-orphan"
    )
    portions: Mapped[list["PortionPain"]] = relationship(  # noqa: F821
        "PortionPain", back_populates="livreur", cascade="all, delete-orphan"
    )
    abonnements: Mapped[list["Abonnement"]] = relationship(  # noqa: F821
        "Abonnement", back_populates="livreur", cascade="all, delete-orphan"
    )
