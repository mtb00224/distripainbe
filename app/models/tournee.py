import enum
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class TypeTournee(str, enum.Enum):
    LIVREUR_PROPRE = "livreur_propre"  # Tournée d'un livreur indépendant

class PeriodeTournee(str, enum.Enum):
    MATIN = "matin"
    SOIR = "soir"

class StatutTournee(str, enum.Enum):
    EN_COURS = "en_cours"
    TERMINEE = "terminee"
    ANNULEE = "annulee"

class Tournee(Base):
    __tablename__ = "tournees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # QUI est le maître de cette tournée ?
    type_tournee: Mapped[TypeTournee] = mapped_column(
        Enum(TypeTournee), nullable=False, default=TypeTournee.LIVREUR_PROPRE
    )

    boulangerie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Si c'est un livreur inscrit (officiel)
    livreur_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("livreurs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Configuration avec ENUMS
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True, default=date.today)
    periode: Mapped[PeriodeTournee] = mapped_column(Enum(PeriodeTournee), nullable=False)
    statut: Mapped[StatutTournee] = mapped_column(
        Enum(StatutTournee), default=StatutTournee.EN_COURS, nullable=False
    )
    
    # Flux de pains
    nb_pains_pris: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nb_pains_ecoules: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nb_pains_retournes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Celui qui a créé la fiche (User connecté)
    created_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Relations
    boulangerie: Mapped["Boulangerie"] = relationship("Boulangerie", back_populates="tournees")
    livreur: Mapped["Livreur | None"] = relationship("Livreur", back_populates="tournees")
    creator: Mapped["User"] = relationship("User")
    livraisons: Mapped[list["LivraisonClient"]] = relationship(
        "LivraisonClient", back_populates="tournee", cascade="all, delete-orphan"
    )
    retour_lignes: Mapped[list["RetourPain"]] = relationship(
        "RetourPain",
        back_populates="tournee",
        cascade="all, delete-orphan"
    )
