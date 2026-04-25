# DistriPain — Backend API

API REST pour le système de gestion des tournées de livraison de pain.

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | JWT (access token + refresh cookie) |
| Base de données | SQLite (dev) / PostgreSQL (prod) |
| Hashage | bcrypt |

## Installation

```bash
cd distripainbe

# Environnement virtuel
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
# .venv\Scripts\activate        # Windows

# Dépendances
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Éditer .env : SECRET_KEY, ADMIN_SETUP_KEY, DATABASE_URL
```

## Lancement

```bash
# Développement (rechargement auto)
uvicorn app.main:app --reload --port 8000
```

- API : http://localhost:8000/api/v1
- Documentation Swagger : http://localhost:8000/docs
- ReDoc : http://localhost:8000/redoc

## Migrations (Alembic)

```bash
# Créer une migration
alembic revision --autogenerate -m "description"

# Appliquer
alembic upgrade head

# Revenir en arrière
alembic downgrade -1
```

> En mode développement, `create_all` crée les nouvelles tables au démarrage mais ne modifie pas les tables existantes — utiliser Alembic pour les changements de schéma.

## Structure du projet

```
app/
├── main.py                  # Point d'entrée FastAPI + CORS + routeurs
├── core/
│   ├── config.py            # Variables d'environnement (Settings)
│   ├── security.py          # JWT, bcrypt, tokens
│   └── dependencies.py      # livreur_only(), require_permission()
├── db/
│   ├── base.py              # Base SQLAlchemy + imports tous les modèles
│   └── session.py           # Engine async, get_db()
├── models/                  # Tables SQLAlchemy
│   ├── livreur.py           # Compte principal (livreur_id, pays_id)
│   ├── acolyte.py           # Sous-compte avec permissions
│   ├── admin.py             # Compte administrateur plateforme
│   ├── client.py            # Client (zone_id, pays_id, prix_vente_pain)
│   ├── zone.py              # Zone de livraison
│   ├── boulangerie.py       # Source d'approvisionnement
│   ├── tournee.py           # Tournée (matin/soir)
│   ├── livraison.py         # Livraison à un client lors d'une tournée
│   ├── retour_boulangerie.py# Retour de pain invendu
│   ├── encaissement.py      # Paiement reçu d'un client
│   ├── dette.py             # Dette client
│   ├── portion_pain.py      # Catalogue de tranches (par livreur)
│   ├── pays.py              # Pays + devise
│   ├── abonnement.py        # Abonnement livreur + paiements
│   ├── moyen_paiement.py    # Moyen de paiement (Wave, Orange Money…)
│   └── user_session.py      # Journal des connexions
├── schemas/                 # Pydantic I/O
├── crud/                    # Opérations DB réutilisables
├── routers/                 # Endpoints REST
│   ├── auth.py              # Inscription, login, refresh, /me
│   ├── boulangeries.py
│   ├── zones.py
│   ├── clients.py
│   ├── tournees.py          # Tournées + livraisons + retour boulangerie
│   ├── encaissements.py     # Encaissements + dettes
│   ├── acolytes.py
│   ├── portions.py          # Portions de pain par livreur
│   ├── stats.py             # Statistiques (journalier/mensuel/annuel…)
│   ├── dettes.py            # Gestion des dettes
│   ├── abonnements.py       # Abonnements livreur + moyens de paiement
│   └── admin.py             # Administration plateforme (protected)
└── services/
    └── stats.py             # Calculs statistiques
```

## Authentification

| Rôle | Mécanisme |
|------|-----------|
| Livreur | JWT access token (30 min) + refresh cookie HttpOnly (7 j) |
| Acolyte | JWT access token + permissions granulaires |
| Admin | JWT Bearer token dédié (header Authorization) |

- Multi-tenant : toutes les requêtes filtrées par `livreur_id` extrait du JWT
- Permissions acolyte : `null` = accès total, `[]` = aucun accès, liste = accès restreint

## Endpoints principaux

### Auth
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | /auth/register | Inscription livreur |
| POST | /auth/login | Connexion (retourne token + set cookie refresh) |
| POST | /auth/refresh | Rafraîchir l'access token |
| GET | /auth/me | Profil utilisateur courant (avec pays) |
| PUT | /auth/profile | Modifier nom/téléphone |
| PUT | /auth/change-password | Changer le mot de passe (livreur) |

### Métier (livreur)
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET/POST | /boulangeries | CRUD boulangeries |
| GET/POST | /zones | CRUD zones |
| GET/POST | /clients | CRUD clients (avec pays/zone) |
| GET/POST | /tournees | CRUD tournées |
| POST | /tournees/{id}/livraisons | Saisir les livraisons |
| GET/POST | /tournees/{id}/retour-boulangerie | Retour pain invendu |
| GET/POST | /encaissements | Encaissements clients |
| GET | /encaissements/pending | Tournées non soldées par client |
| GET/POST | /dettes | Gestion des dettes |
| POST | /dettes/{id}/reglements | Règlement partiel/total |
| GET/POST | /acolytes | CRUD sous-comptes |
| GET/POST | /portions | Catalogue de tranches de pain |
| GET | /stats/journalier | Stats du jour |
| GET | /stats/mensuel | Stats mensuelles |
| GET | /stats/annuel | Stats annuelles |

### Abonnements (livreur)
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | /abonnements/formules | Formules disponibles (filtrées par pays) |
| GET | /abonnements/moyens-paiement | Moyens de paiement (filtrés par pays) |
| GET | /abonnements/current | Abonnement courant |
| POST | /abonnements | Souscrire à une formule |
| POST | /abonnements/{id}/paiement | Déclarer un paiement |
| GET | /abonnements/history | Historique des abonnements |

### Administration
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | /admin/auth/login | Connexion admin |
| GET | /admin/stats | Statistiques plateforme |
| GET/PATCH | /admin/livreurs | Liste et gestion des livreurs |
| GET | /admin/livreurs/{id} | Détail livreur + performances |
| GET/PUT | /admin/livreurs/{id}/permissions | Permissions acolytes |
| GET/POST | /admin/pays | CRUD pays et devises |
| GET/POST | /admin/formules-abonnement | CRUD formules d'abonnement |
| GET | /admin/abonnements | Liste abonnements + validation paiements |
| GET/POST | /admin/moyens-paiement | CRUD moyens de paiement |
| GET | /admin/traffic | Journal des connexions |

Un changement sur l'état actuelle
