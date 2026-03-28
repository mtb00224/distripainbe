from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Acolyte(Base):
    __tablename__ = "acolytes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_principal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    # JSON list e.g. '["read_clients","write_tournees"]'
    permissions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    is_default_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    livreur_principal: Mapped["Livreur"] = relationship(  # noqa: F821
        "Livreur", back_populates="acolytes"
    )
