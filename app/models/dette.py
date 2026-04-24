from datetime import datetime, timezone
from decimal import Decimal
import enum
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class DetteStatut(str, enum.Enum):
    EN_COURS = "en_cours"
    PARTIELLEMENT_SOLDEE = "partiellement_soldee"
    SOLDEE = "soldee"
    ANNULEE = "annulee"

class Dette(Base):
    """Registre des dettes — Gère ce que les clients doivent aux livreurs ou boulangeries."""
    __tablename__ = "dettes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Propriétaire de la créance
    livreur_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    boulangerie_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    # Le débiteur (celui qui doit l'argent)
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Lien optionnel avec la vente d'origine
    encaissement_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("encaissements.id", ondelete="SET NULL"), nullable=True
    )
    
    montant_initial: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    montant_restant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Utilisation de l'Enum pour le statut
    statut: Mapped[DetteStatut] = mapped_column(
        Enum(DetteStatut), nullable=False, default=DetteStatut.EN_COURS
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relations
    client: Mapped["Client"] = relationship("Client", back_populates="dettes", foreign_keys=[client_id])
    reglements: Mapped[list["ReglementDette"]] = relationship(
        "ReglementDette", back_populates="dette", cascade="all, delete-orphan"
    )
    
    # Propriété calculée pour voir le total déjà payé sans requête complexe
    @property
    def total_paye(self) -> Decimal:
        return sum(r.montant for r in self.reglements)

class ReglementDette(Base):
    """Historique des versements pour rembourser une dette."""
    __tablename__ = "reglements_dette"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dette_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dettes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Destination des fonds
    livreur_id: Mapped[int | None] = mapped_column(ForeignKey("livreurs.id"), nullable=True)
    boulangerie_id: Mapped[int | None] = mapped_column(ForeignKey("boulangeries.id"), nullable=True)
    
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    date_reglement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Celui qui a validé la réception de l'argent
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relations
    dette: Mapped["Dette"] = relationship("Dette", back_populates="reglements")
    user: Mapped["User"] = relationship("User") 
