from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        
    livreur_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    boulangerie_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    # Un client appartient généralement à une Zone
    zone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )

    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Prix spécifique pratiqué pour ce client
    prix_vente_pain: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Ce que le client doit (Balance). Si > 0, c'est une dette.
    solde_actuel: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    livreur: Mapped["Livreur | None"] = relationship("Livreur", back_populates="clients")
    boulangerie: Mapped["Boulangerie | None"] = relationship("Boulangerie")
    zone: Mapped["Zone | None"] = relationship("Zone", back_populates="clients")
    
    livraisons: Mapped[list["LivraisonClient"]] = relationship(
        "LivraisonClient", back_populates="client", cascade="all, delete-orphan"
    )
    encaissements: Mapped[list["Encaissement"]] = relationship(
        "Encaissement", back_populates="client"
    )
    # Lien vers ses dettes pour un accès rapide
    dettes: Mapped[list["Dette"]] = relationship("Dette", back_populates="client")
    creator: Mapped["User"] = relationship("User")
