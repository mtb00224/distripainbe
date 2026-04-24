from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import de tous les modèles pour qu'Alembic puisse les détecter
from app.models.user import User, UserSession  # noqa: F401, E402
from app.models.livreur import Livreur, AcolyteLivreur, LivreurBoulangerie  # noqa: F401, E402
from app.models.refresh_token import RefreshToken  # noqa: F401, E402
from app.models.boulangerie import (  # noqa: F401, E402
    Boulangerie, AdminBoulangerie, StaffBoulangerie, CategorieDepense, Depense, PortionPainBoulangerie
)
from app.models.zone import Zone  # noqa: F401, E402
from app.models.client import Client  # noqa: F401, E402
from app.models.tournee import Tournee  # noqa: F401, E402
from app.models.livraison_client import LivraisonClient  # noqa: F401, E402
from app.models.encaissement import Encaissement  # noqa: F401, E402
from app.models.portion_pain import PortionPain  # noqa: F401, E402
from app.models.retour_pain import RetourPain  # noqa: F401, E402
from app.models.dette import Dette, ReglementDette  # noqa: F401, E402
from app.models.abonnement import (  # noqa: F401, E402
    FormulaAbonnement, Abonnement, PaiementAbonnement, MoyenPaiement
)
from app.models.livreur_interne import (  # noqa: F401, E402
    LivreurInterne, CompteInterneLivreur, RetirementCompte
)
from app.models.production import (  # noqa: F401, E402
    SessionProduction, DistributionLivreur, RetourDistributionLigne
)
from app.models.livreur_interne_portion import LivreurInternePortionPain  # noqa: F401, E402
from app.models.client_portion import ClientPortionPain  # noqa: F401, E402
from app.models.dette_boulangerie import DetteBoulangerie, ReglementDetteBoulangerie  # noqa: F401, E402
from app.models.vente_ambulatoire import ProduitAmbulateur  # noqa: F401, E402
