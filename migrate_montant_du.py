"""Migration : ajoute la colonne montant_du à livraisons_clients.

SQLite supporte ALTER TABLE ADD COLUMN si la colonne a un DEFAULT.
Les lignes existantes auront montant_du = 0 (à recalculer manuellement si besoin).

Utilisation :
    python migrate_montant_du.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "dev.db")


def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Vérifier si la colonne existe déjà
    cur.execute("PRAGMA table_info(livraisons_clients)")
    columns = [row[1] for row in cur.fetchall()]

    if "montant_du" in columns:
        print("La colonne montant_du existe déjà.")
    else:
        cur.execute(
            "ALTER TABLE livraisons_clients ADD COLUMN montant_du NUMERIC(12, 2) NOT NULL DEFAULT 0"
        )
        # Recalculer montant_du pour les lignes existantes
        cur.execute(
            """
            UPDATE livraisons_clients
            SET montant_du = (nb_pains_livres - nb_pains_retournes) * prix_unitaire
            WHERE montant_du = 0
            """
        )
        conn.commit()
        print(f"Colonne montant_du ajoutée et recalculée ({cur.rowcount} lignes mises à jour).")

    conn.close()


if __name__ == "__main__":
    run()
