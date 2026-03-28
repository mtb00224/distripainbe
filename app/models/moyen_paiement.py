from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MoyenPaiement(Base):
    __tablename__ = "moyens_paiement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pays_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pays.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nom: Mapped[str] = mapped_column(String(50), nullable=False)   # Wave, Orange Money…
    numero: Mapped[str] = mapped_column(String(30), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    pays: Mapped["Pays | None"] = relationship(  # noqa: F821
        "Pays", back_populates="moyens_paiement"
    )
