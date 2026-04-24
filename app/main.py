from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routers import (
    auth, boulangeries, zones, clients, tournees,
    encaissements, acolytes, stats, portions, admin,
    dettes, abonnements, commons, admin_boulangerie,
    livreurs_internes, production,
    depenses_boulangerie, stats_boulangerie, portions_boulangerie,
    livreur_interne_portions, client_portions, dettes_boulangerie,
    ventes_ambulatoires,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="DistriPain API",
    description="Système de gestion des tournées de livraison de pain",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(commons.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(admin_boulangerie.router, prefix=API_PREFIX)
app.include_router(boulangeries.router, prefix=API_PREFIX)
app.include_router(zones.router, prefix=API_PREFIX)
app.include_router(clients.router, prefix=API_PREFIX)
app.include_router(tournees.router, prefix=API_PREFIX)
app.include_router(encaissements.router, prefix=API_PREFIX)
app.include_router(acolytes.router, prefix=API_PREFIX)
app.include_router(stats.router, prefix=API_PREFIX)
app.include_router(portions.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)
app.include_router(dettes.router, prefix=API_PREFIX)
app.include_router(abonnements.router, prefix=API_PREFIX)
app.include_router(livreurs_internes.router, prefix=API_PREFIX)
app.include_router(production.router, prefix=API_PREFIX)
app.include_router(depenses_boulangerie.router, prefix=API_PREFIX)
app.include_router(stats_boulangerie.router, prefix=API_PREFIX)
app.include_router(portions_boulangerie.router, prefix=API_PREFIX)
app.include_router(livreur_interne_portions.router, prefix=API_PREFIX)
app.include_router(client_portions.router, prefix=API_PREFIX)
app.include_router(dettes_boulangerie.router, prefix=API_PREFIX)
app.include_router(ventes_ambulatoires.router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
