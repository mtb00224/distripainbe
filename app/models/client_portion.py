from decimal import Decimal
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClientPortionPain(Base):
    """
    Portion de pain configurable par client (côté livreur indépendant).
    Chaque client a ses propres portions avec ses propres prix.
    Ex : Client A → Pain entier à 175 FCFA ; Client B → Pain entier à 160 FCFA.
    """
    __tablename__ = "client_portions_pain"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    livreur_id: Mapped[int] = mapped_column(
        ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prix_fcfa: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valeur_unitaire: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("1.0"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client: Mapped["Client"] = relationship("Client")
    livreur: Mapped["Livreur"] = relationship("Livreur")
