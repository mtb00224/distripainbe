from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tournee(Base):
    __tablename__ = "tournees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    boulangerie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boulangeries.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_acolyte_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("acolytes.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # 'matin' or 'soir'
    periode: Mapped[str] = mapped_column(String(10), nullable=False)
    nb_pains_pris: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nb_pains_ecoules: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nb_pains_retournes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 'en_cours', 'terminee', 'annulee'
    statut: Mapped[str] = mapped_column(String(20), default="en_cours", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    livreur: Mapped["Livreur"] = relationship("Livreur", back_populates="tournees")  # noqa: F821
    boulangerie: Mapped["Boulangerie"] = relationship("Boulangerie", back_populates="tournees")  # noqa: F821
    livraisons: Mapped[list["LivraisonClient"]] = relationship(  # noqa: F821
        "LivraisonClient", back_populates="tournee", cascade="all, delete-orphan"
    )
