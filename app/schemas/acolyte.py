from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr

AVAILABLE_PERMISSIONS = [
    # Clients
    "read_clients",        # Voir la liste et le détail des clients
    "write_clients",       # Ajouter / modifier / désactiver un client
    # Boulangeries
    "read_boulangeries",   # Voir les boulangeries
    "write_boulangeries",  # Ajouter / modifier une boulangerie
    # Zones
    "read_zones",          # Voir les zones
    "write_zones",         # Ajouter / modifier une zone
    # Tournées
    "read_tournees",       # Consulter les tournées
    "create_tournees",     # Créer une nouvelle tournée
    "update_tournees",     # Modifier les chiffres d'une tournée (pains pris, boulangerie…)
    "terminer_tournees",   # Clôturer une tournée
    # Livraisons
    "write_livraisons",    # Ajouter / modifier / supprimer les livraisons d'une tournée
    # Encaissements
    "read_encaissements",  # Voir les encaissements
    "write_encaissements", # Enregistrer un paiement
    # Statistiques
    "read_stats",          # Consulter les statistiques
]


class AcolyteCreate(BaseModel):
    nom: str
    email: EmailStr
    permissions: list[str] = []


class AcolyteUpdate(BaseModel):
    nom: Optional[str] = None
    email: Optional[EmailStr] = None
    permissions: Optional[list[str]] = None
    is_active: Optional[bool] = None


class AcolyteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livreur_principal_id: int
    nom: str
    email: str
    permissions: list[str]
    is_default_password: bool
    is_active: bool
    created_at: datetime

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        import json
        if hasattr(obj, 'permissions') and isinstance(obj.permissions, str):
            try:
                obj.permissions = json.loads(obj.permissions)
            except (ValueError, TypeError):
                obj.permissions = []
        return super().model_validate(obj, *args, **kwargs)
