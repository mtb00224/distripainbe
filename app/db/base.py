from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models here so Alembic can detect them
from app.models.livreur import Livreur  # noqa: F401, E402
from app.models.acolyte import Acolyte  # noqa: F401, E402
from app.models.refresh_token import RefreshToken  # noqa: F401, E402
from app.models.boulangerie import Boulangerie  # noqa: F401, E402
from app.models.zone import Zone  # noqa: F401, E402
from app.models.client import Client  # noqa: F401, E402
from app.models.tournee import Tournee  # noqa: F401, E402
from app.models.livraison_client import LivraisonClient  # noqa: F401, E402
from app.models.encaissement import Encaissement  # noqa: F401, E402
from app.models.portion_pain import PortionPain  # noqa: F401, E402
from app.models.admin import Admin  # noqa: F401, E402
from app.models.user_session import UserSession  # noqa: F401, E402
from app.models.retour_boulangerie import RetourBoulangerieLigne  # noqa: F401, E402
from app.models.dette import Dette, ReglementDette  # noqa: F401, E402
from app.models.pays import Pays  # noqa: F401, E402
from app.models.abonnement import FormulaAbonnement, Abonnement, PaiementAbonnement  # noqa: F401, E402
from app.models.moyen_paiement import MoyenPaiement  # noqa: F401, E402
