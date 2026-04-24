"""Catalogue des produits de vente ambulatoire par boulangerie."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProduitAmbulateur(Base):
    __tablename__ = "produits_ambulatoires"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    boulangerie_id: Mapped[int] = mapped_column(
        ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unite: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # ex: "pièce", "kg"
    prix_unitaire: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    boulangerie: Mapped["Boulangerie"] = relationship("Boulangerie", back_populates="produits_ambulatoires")
