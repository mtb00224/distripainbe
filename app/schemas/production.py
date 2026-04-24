from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

from app.models.production import ModeReglement, PeriodeJournee, StatutDistribution, StatutSession


# ─────────────────────────────────────────────
# Distribution
# ─────────────────────────────────────────────

class DistributionCreate(BaseModel):
    livreur_interne_id: int
    nb_pains_donnes: int
    # Si non renseigné, on prend le prix_achat_pain du LivreurInterne
    prix_par_pain: Optional[Decimal] = None


class RetourLigneBoulangerieIn(BaseModel):
    portion_id: int
    quantite: int = 0


class DistributionUpdate(BaseModel):
    nb_pains_retournes: Optional[int] = None
    montant_encaisse: Optional[Decimal] = None
    mode_reglement: Optional[ModeReglement] = None
    statut: Optional[StatutDistribution] = None
    notes: Optional[str] = None
    lignes_retour: Optional[List[RetourLigneBoulangerieIn]] = None


class DistributionLivreurResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    livreur_interne_id: int
    nb_pains_donnes: int
    prix_par_pain: Decimal
    nb_pains_retournes: int
    montant_encaisse: Decimal
    mode_reglement: ModeReglement
    statut: StatutDistribution
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Calculés (depuis @property du modèle)
    nb_pains_vendus: int
    montant_theorique: Decimal
    ecart: Decimal

    # Infos du livreur interne (pour affichage)
    livreur_prenom: Optional[str] = None
    livreur_nom: Optional[str] = None

    @classmethod
    def from_orm_enriched(cls, dist) -> "DistributionLivreurResponse":
        return cls(
            id=dist.id,
            session_id=dist.session_id,
            livreur_interne_id=dist.livreur_interne_id,
            nb_pains_donnes=dist.nb_pains_donnes,
            prix_par_pain=dist.prix_par_pain,
            nb_pains_retournes=dist.nb_pains_retournes,
            montant_encaisse=dist.montant_encaisse,
            mode_reglement=dist.mode_reglement,
            statut=dist.statut,
            notes=dist.notes,
            created_at=dist.created_at,
            updated_at=dist.updated_at,
            nb_pains_vendus=dist.nb_pains_vendus,
            montant_theorique=dist.montant_theorique,
            ecart=dist.ecart,
            livreur_prenom=dist.livreur_interne.prenom if dist.livreur_interne else None,
            livreur_nom=dist.livreur_interne.nom if dist.livreur_interne else None,
        )


# ─────────────────────────────────────────────
# Session de production
# ─────────────────────────────────────────────

class SessionProductionCreate(BaseModel):
    date: date
    periode: PeriodeJournee
    nb_pains_produits: int
    nb_pains_ambulatoire: int = 0
    notes: Optional[str] = None


class SessionProductionUpdate(BaseModel):
    nb_pains_produits: Optional[int] = None
    nb_pains_ambulatoire: Optional[int] = None
    notes: Optional[str] = None


class SessionProductionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    boulangerie_id: int
    date: date
    periode: PeriodeJournee
    nb_pains_produits: int
    nb_pains_ambulatoire: int
    montant_ambulatoire: Decimal
    statut: StatutSession
    notes: Optional[str] = None
    created_at: datetime

    # Calculés
    nb_pains_distribues: int
    nb_pains_retournes_total: int
    nb_pains_vendus_total: int
    montant_encaisse_total: Decimal
    nb_pains_non_distribues: int

    distributions: List[DistributionLivreurResponse] = []


# ─────────────────────────────────────────────
# Fournisseur (boulangerie côté livreur)
# ─────────────────────────────────────────────

class FournisseurCreate(BaseModel):
    """Créer une nouvelle boulangerie comme fournisseur (sans admin système)."""
    nom: str
    contact: Optional[str] = None
    address: Optional[str] = None
    prix_achat_pain: Optional[Decimal] = None
    contact_local: Optional[str] = None


class FournisseurLinkRequest(BaseModel):
    """Lier à une boulangerie existante dans le système."""
    boulangerie_id: int
    prix_achat_pain: Optional[Decimal] = None
    contact_local: Optional[str] = None


class FournisseurContratUpdate(BaseModel):
    prix_achat_pain: Optional[Decimal] = None
    contact_local: Optional[str] = None
    is_active: Optional[bool] = None


class FournisseurResponse(BaseModel):
    """Boulangerie + infos du contrat livreur."""
    id: int
    nom: str
    contact: Optional[str] = None
    address: Optional[str] = None
    is_active_boulangerie: bool
    # Contrat
    prix_achat_pain: Optional[Decimal] = None
    contact_local: Optional[str] = None
    lien_actif: bool
    # True si gérée par un AdminBoulangerie inscrit sur la plateforme
    is_managed: bool
