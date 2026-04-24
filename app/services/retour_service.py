# app/services/cloture_service.py
import math
from decimal import Decimal

def finaliser_retour(lignes_retour):
    """
    Calcule l'argent et le stock à partir des lignes de retour d'une tournée.
    """
    total_argent = Decimal("0.0")
    total_fractions = Decimal("0.0")
    
    for ligne in lignes_retour:
        # ligne.portion est chargé via la relation SQLAlchemy
        total_argent += ligne.quantite * ligne.portion.prix_fcfa
        total_fractions += Decimal(str(ligne.quantite)) * ligne.portion.valeur_unitaire
    
    return {
        "argent_a_deduire": total_argent,
        "pains_recomposes": math.floor(total_fractions),
        "reste_miettes": float(total_fractions % 1)
    }
