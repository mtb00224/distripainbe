from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RetourBoulangerieLigne(Base):
    __tablename__ = "retour_boulangerie_lignes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portion_pain_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portions_pain.id", ondelete="CASCADE"), nullable=False
    )
    quantite: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    portion: Mapped["PortionPain"] = relationship("PortionPain")  # noqa: F821
