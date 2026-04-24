import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PeriodeJournee(str, enum.Enum):
    MATIN = "matin"
    SOIR  = "soir"


class StatutSession(str, enum.Enum):
    OUVERTE   = "ouverte"    # En cours — on peut encore modifier
    CLOTUREE  = "cloturee"   # Clôturée — lecture seule


class ModeReglement(str, enum.Enum):
    CASH            = "cash"            # Paiement cash immédiat
    COMPTE_INTERNE  = "compte_interne"  # Gardé dans le compte interne de la boulangerie
    VIREMENT        = "virement"        # Wave / Orange Money / virement bancaire
    CREDIT          = "credit"          # Laissé en dette (à régler plus tard)


class StatutDistribution(str, enum.Enum):
    EN_ATTENTE = "en_attente"  # Pain distribué, retour/paiement pas encore saisi
    SOLDE      = "solde"       # Tout clôturé (retours + encaissement confirmés)
    ANNULE     = "annule"      # Distribution annulée (erreur, livreur absent, etc.)


class SessionProduction(Base):
    """
    Journal de production journalier d'une boulangerie.
    Remplace la notion de 'tournée' côté boulangerie.
    Ex: Lundi matin → 500 pains produits, 50 vendus en ambulatoire,
        reste distribué aux livreurs internes.
    """
    __tablename__ = "sessions_production"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boulangerie_id: Mapped[int] = mapped_column(
        ForeignKey("boulangeries.id", ondelete="CASCADE"), nullable=False, index=True
    )

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    periode: Mapped[PeriodeJournee] = mapped_column(
        Enum(PeriodeJournee), nullable=False
    )

    nb_pains_produits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Vente ambulatoire : pain vendu directement par le staff de la boulangerie
    nb_pains_ambulatoire: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    montant_ambulatoire: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    statut: Mapped[StatutSession] = mapped_column(
        Enum(StatutSession), default=StatutSession.OUVERTE, nullable=False
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relations
    boulangerie: Mapped["Boulangerie"] = relationship("Boulangerie", back_populates="sessions_production")
    distributions: Mapped[list["DistributionLivreur"]] = relationship(
        "DistributionLivreur", back_populates="session", cascade="all, delete-orphan"
    )
    creator: Mapped["User"] = relationship("User")

    # ── Propriétés calculées ──────────────────────────────────────────────────

    @property
    def nb_pains_distribues(self) -> int:
        return sum(d.nb_pains_donnes for d in self.distributions)

    @property
    def nb_pains_retournes_total(self) -> int:
        return sum(d.nb_pains_retournes for d in self.distributions)

    @property
    def nb_pains_vendus_total(self) -> int:
        return sum(d.nb_pains_vendus for d in self.distributions) + self.nb_pains_ambulatoire

    @property
    def montant_encaisse_total(self) -> Decimal:
        return sum(d.montant_encaisse for d in self.distributions) + self.montant_ambulatoire

    @property
    def nb_pains_non_distribues(self) -> int:
        return self.nb_pains_produits - self.nb_pains_distribues - self.nb_pains_ambulatoire


class DistributionLivreur(Base):
    """
    Une ligne de distribution : combien de pains ce livreur interne a pris,
    combien il a retourné, combien il a encaissé.
    """
    __tablename__ = "distributions_livreur"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions_production.id", ondelete="CASCADE"), nullable=False, index=True
    )
    livreur_interne_id: Mapped[int] = mapped_column(
        ForeignKey("livreurs_internes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    nb_pains_donnes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Prix unitaire au moment de la distribution (peut différer du prix par défaut)
    prix_par_pain: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Saisis en fin de journée / lors de la clôture
    nb_pains_retournes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    montant_encaisse: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    mode_reglement: Mapped[ModeReglement] = mapped_column(
        Enum(ModeReglement), default=ModeReglement.CASH, nullable=False
    )
    statut: Mapped[StatutDistribution] = mapped_column(
        Enum(StatutDistribution), default=StatutDistribution.EN_ATTENTE, nullable=False
    )

    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relations
    session: Mapped["SessionProduction"] = relationship(
        "SessionProduction", back_populates="distributions"
    )
    livreur_interne: Mapped["LivreurInterne"] = relationship(
        "LivreurInterne", back_populates="distributions"
    )
    lignes_retour: Mapped[list["RetourDistributionLigne"]] = relationship(
        "RetourDistributionLigne", back_populates="distribution", cascade="all, delete-orphan"
    )

    # ── Propriétés calculées ──────────────────────────────────────────────────

    @property
    def nb_pains_vendus(self) -> int:
        return max(0, self.nb_pains_donnes - self.nb_pains_retournes)

    @property
    def montant_theorique(self) -> Decimal:
        """Ce que le livreur devrait rendre si tout est vendu au prix convenu."""
        return Decimal(self.nb_pains_vendus) * self.prix_par_pain

    @property
    def ecart(self) -> Decimal:
        """Différence entre ce qui a été encaissé et ce qui était attendu."""
        return self.montant_encaisse - self.montant_theorique


class RetourDistributionLigne(Base):
    """Détail des morceaux de pain retournés par un livreur interne (par portion)."""
    __tablename__ = "retour_distribution_lignes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    distribution_id: Mapped[int] = mapped_column(
        ForeignKey("distributions_livreur.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portion_id: Mapped[int] = mapped_column(
        ForeignKey("livreur_interne_portions.id", ondelete="CASCADE"), nullable=False
    )
    quantite: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    distribution: Mapped["DistributionLivreur"] = relationship("DistributionLivreur", back_populates="lignes_retour")
    portion: Mapped["LivreurInternePortionPain"] = relationship("LivreurInternePortionPain")
