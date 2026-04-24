import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class AbonnementStatut(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    ACTIF = "actif"
    EXPIRE = "expire"
    SUSPENDU = "suspendu"

class PaiementStatut(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    VALIDE = "valide"
    REJETE = "rejete"

class CibleAbonnement(str, enum.Enum):
    LIVREUR = "livreur"
    BOULANGER = "boulanger"

# --- Tables de Configuration ---
class MoyenPaiement(Base):
    """Les comptes de l'Admin (ton Wave, ton Orange Money) pour recevoir l'argent."""
    __tablename__ = "moyens_paiement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)    
    nom: Mapped[str] = mapped_column(String(50)) # Wave, Orange Money, Cash
    numero: Mapped[str] = mapped_column(String(30))
    instructions: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class FormulaAbonnement(Base):
    __tablename__ = "formules_abonnement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # À qui s'adresse cette offre ?
    cible: Mapped[CibleAbonnement] = mapped_column(
        Enum(CibleAbonnement), nullable=False, default=CibleAbonnement.LIVREUR
    )
    
    # Nombre max de boulangeries autorisées (Uniquement pour la cible BOULANGER)
    # On le met à None (null) pour les livreurs.
    max_boulangeries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    duree_mois: Mapped[int] = mapped_column(Integer, nullable=False) # 1, 3, 12...
    prix: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    abonnements: Mapped[list["Abonnement"]] = relationship(
        "Abonnement", back_populates="formule"
    )


# --- Tables de Transaction ---
class Abonnement(Base):
    __tablename__ = "abonnements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # L'un des deux doit être rempli
    livreur_id: Mapped[int | None] = mapped_column(ForeignKey("livreurs.id", ondelete="CASCADE"), nullable=True)
    boulangerie_id: Mapped[int | None] = mapped_column(ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=True)
    
    formule_id: Mapped[int] = mapped_column(ForeignKey("formules_abonnement.id"))
    
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date] = mapped_column(Date)
    
    statut: Mapped[AbonnementStatut] = mapped_column(Enum(AbonnementStatut), default=AbonnementStatut.EN_ATTENTE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    formule: Mapped["FormulaAbonnement"] = relationship("FormulaAbonnement", back_populates="abonnements")
    paiements: Mapped[list["PaiementAbonnement"]] = relationship("PaiementAbonnement", back_populates="abonnement")
    livreur: Mapped["Livreur"] = relationship("Livreur", back_populates="abonnements", foreign_keys=[livreur_id])

class PaiementAbonnement(Base):
    __tablename__ = "paiements_abonnement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    abonnement_id: Mapped[int] = mapped_column(ForeignKey("abonnements.id", ondelete="CASCADE"))
    
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reference: Mapped[str | None] = mapped_column(String(100)) # ID de transaction Wave/OM
    
    statut: Mapped[PaiementStatut] = mapped_column(Enum(PaiementStatut), default=PaiementStatut.EN_ATTENTE)
    date_paiement: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Qui a validé ce paiement (Admin) ?
    valide_par_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    abonnement: Mapped["Abonnement"] = relationship("Abonnement", back_populates="paiements")
