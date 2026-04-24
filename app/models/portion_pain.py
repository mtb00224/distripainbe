from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class TypePain(Base):
    """Référentiel Admin : Définit les catégories (Pain Simple, Pain Beurre, etc.)"""
    __tablename__ = "types_pain"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    nom: Mapped[str] = mapped_column(String(50), unique=True, nullable=False) 
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User")

class PortionPain(Base):
    """Configuration des portions (Entier, 1/2, morceaux de 50, 75, 100, etc.)"""
    __tablename__ = "portions_pain"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_pain_id: Mapped[int | None] = mapped_column(ForeignKey("types_pain.id"), nullable=True)
    
    boulangerie_id: Mapped[int | None] = mapped_column(ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=True)
    livreur_id: Mapped[int | None] = mapped_column(ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=True)
    
    nom: Mapped[str] = mapped_column(String(100), nullable=False) # Ex: "Morceau de 75"
    prix_fcfa: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # --- CHAMP CLÉ POUR L'ÉQUIVALENCE ---
    # Représente la fraction du pain entier. 
    # Ex: Entier = 1.0 | 75f = 0.5 | 50f = 0.33 | 100f = 0.66
    valeur_unitaire: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=1.0, nullable=False) 
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relations
    type_reference: Mapped["TypePain"] = relationship("TypePain")
    boulangerie: Mapped["Boulangerie"] = relationship("Boulangerie")
    livreur: Mapped["Livreur"] = relationship("Livreur")
