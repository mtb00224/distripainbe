from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routers import auth, boulangeries, zones, clients, tournees, encaissements, acolytes, stats
from app.routers import portions, admin, dettes, abonnements


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (dev mode)
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="DistriPain API",
    description="Système de gestion des tournées de livraison de pain",
    version="1.0.0",
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

app.include_router(auth.router, prefix=API_PREFIX)
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


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
