from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Boulangerie(Base):
    __tablename__ = "boulangeries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prix_achat_pain: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    livreur: Mapped["Livreur"] = relationship("Livreur", back_populates="boulangeries")  # noqa: F821
    tournees: Mapped[list["Tournee"]] = relationship("Tournee", back_populates="boulangerie")  # noqa: F821
