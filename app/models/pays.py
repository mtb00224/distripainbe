from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Pays(Base):
    __tablename__ = "pays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)  # GN, SN…
    devise_nom: Mapped[str] = mapped_column(String(50), nullable=False)   # Franc Guinéen
    devise_code: Mapped[str] = mapped_column(String(10), nullable=False)  # GNF
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    clients: Mapped[list["Client"]] = relationship(  # noqa: F821
        "Client", back_populates="pays"
    )
    moyens_paiement: Mapped[list["MoyenPaiement"]] = relationship(  # noqa: F821
        "MoyenPaiement", back_populates="pays", cascade="all, delete-orphan"
    )
