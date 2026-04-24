from decimal import Decimal
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LivreurInternePortionPain(Base):
    """
    Portion de pain configurable par livreur interne.
    Chaque livreur peut avoir ses propres portions avec ses propres prix d'achat.
    Ex : Ali → Demi-pain à 55 FCFA ; Moussa → Demi-pain à 50 FCFA.
    """
    __tablename__ = "livreur_interne_portions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    livreur_interne_id: Mapped[int] = mapped_column(
        ForeignKey("livreurs_internes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prix_achat: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    equivalent_pains: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    livreur_interne: Mapped["LivreurInterne"] = relationship(
        "LivreurInterne", back_populates="portions"
    )
