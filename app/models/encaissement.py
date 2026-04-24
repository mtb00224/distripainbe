import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class TypeEncaissement(str, enum.Enum):
    COMPLET = "complet"
    PARTIEL = "partiel"
    AVANCE = "avance"
    DETTE = "dette"

class Encaissement(Base):
    __tablename__ = "encaissements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Propriétaire du cash (Qui encaisse ?)
    livreur_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    boulangerie_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=True, index=True
    )

    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # L'humain qui a physiquement reçu l'argent
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    date_encaissement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # IDs des livraisons payées par cet argent
    livraisons_soldees: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    
    # Enum pour le type
    type: Mapped[TypeEncaissement] = mapped_column(
        Enum(TypeEncaissement), nullable=False
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    livreur: Mapped["Livreur | None"] = relationship("Livreur", back_populates="encaissements")
    boulangerie: Mapped["Boulangerie | None"] = relationship("Boulangerie")
    client: Mapped["Client"] = relationship("Client", back_populates="encaissements")
    user: Mapped["User"] = relationship("User")