from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class RetourPain(Base):
    """
    Détail précis des pains rendus à la fin de la tournée.
    Permet au livreur et à la boulangerie de valider les retours par type de pain.
    """
    __tablename__ = "retour_boulangerie_lignes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    tournee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Précise quelle portion est retournée (Baguette, Miche, etc.)
    portion_pain_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portions_pain.id", ondelete="CASCADE"), nullable=False
    )
    
    quantite: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relations
    tournee: Mapped["Tournee"] = relationship("Tournee", back_populates="retour_lignes")
    portion: Mapped["PortionPain"] = relationship("PortionPain")
