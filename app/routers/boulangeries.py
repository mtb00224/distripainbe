"""Boulangeries du point de vue du livreur indépendant.

Un livreur peut :
- Lister ses boulangeries fournisseur (celles auxquelles il est lié)
- Créer une nouvelle entrée boulangerie comme fournisseur
- Lier son compte à une boulangerie existante dans le système
- Modifier son contrat (prix d'achat, contact local)
- Se délier d'une boulangerie
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_livreur, livreur_only, require_permission
from app.db.session import get_db
from app.models.boulangerie import Boulangerie
from app.models.livreur import Livreur, LivreurBoulangerie
from app.schemas.boulangerie import BoulangerieResponse
from app.schemas.production import (
    FournisseurContratUpdate,
    FournisseurCreate,
    FournisseurLinkRequest,
    FournisseurResponse,
)

router = APIRouter(prefix="/boulangeries", tags=["boulangeries"])


def _build_fournisseur_response(b: Boulangerie, lien: LivreurBoulangerie) -> FournisseurResponse:
    return FournisseurResponse(
        id=b.id,
        nom=b.nom,
        contact=b.contact,
        address=b.address,
        is_active_boulangerie=b.is_active,
        prix_achat_pain=lien.prix_achat_pain,
        contact_local=lien.contact_local,
        lien_actif=lien.is_active,
        is_managed=b.admin_boulangerie_id is not None,
    )


@router.get("", response_model=list[FournisseurResponse])
async def list_boulangeries(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_boulangeries")),
):
    """Liste les boulangeries fournisseur de ce livreur avec les infos de contrat."""
    stmt = (
        select(Boulangerie, LivreurBoulangerie)
        .join(LivreurBoulangerie, LivreurBoulangerie.boulangerie_id == Boulangerie.id)
        .where(LivreurBoulangerie.livreur_id == livreur.id)
    )
    if not include_inactive:
        stmt = stmt.where(
            Boulangerie.is_active == True,
            LivreurBoulangerie.is_active == True,
        )
    result = await db.execute(stmt.order_by(Boulangerie.nom))
    return [_build_fournisseur_response(b, lien) for b, lien in result.all()]


@router.get("/{boulangerie_id}", response_model=FournisseurResponse)
async def get_boulangerie(
    boulangerie_id: int,
    db: AsyncSession = Depends(get_db),
    livreur: Livreur = Depends(require_permission("read_boulangeries")),
):
    result = await db.execute(
        select(Boulangerie, LivreurBoulangerie)
        .join(LivreurBoulangerie, LivreurBoulangerie.boulangerie_id == Boulangerie.id)
        .where(
            Boulangerie.id == boulangerie_id,
            LivreurBoulangerie.livreur_id == livreur.id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")
    return _build_fournisseur_response(row[0], row[1])


@router.post("", response_model=FournisseurResponse, status_code=status.HTTP_201_CREATED)
async def create_fournisseur(
    payload: FournisseurCreate,
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    """Crée une nouvelle boulangerie comme fournisseur (entrée de référence, sans admin système)."""
    b = Boulangerie(
        nom=payload.nom,
        contact=payload.contact,
        address=payload.address,
        admin_boulangerie_id=None,
    )
    db.add(b)
    await db.flush()

    lien = LivreurBoulangerie(
        livreur_id=livreur.id,
        boulangerie_id=b.id,
        prix_achat_pain=payload.prix_achat_pain,
        contact_local=payload.contact_local,
    )
    db.add(lien)
    await db.commit()
    await db.refresh(b)
    await db.refresh(lien)
    return _build_fournisseur_response(b, lien)


@router.post("/link", response_model=FournisseurResponse, status_code=status.HTTP_201_CREATED)
async def link_fournisseur(
    payload: FournisseurLinkRequest,
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    """Lie ce livreur à une boulangerie existante dans le système."""
    b_result = await db.execute(
        select(Boulangerie).where(Boulangerie.id == payload.boulangerie_id, Boulangerie.is_active == True)
    )
    b = b_result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable ou inactive")

    # Vérifier si déjà lié
    existing = await db.execute(
        select(LivreurBoulangerie).where(
            LivreurBoulangerie.livreur_id == livreur.id,
            LivreurBoulangerie.boulangerie_id == b.id,
        )
    )
    lien = existing.scalar_one_or_none()
    if lien:
        if lien.is_active:
            raise HTTPException(status_code=400, detail="Vous êtes déjà lié à cette boulangerie")
        # Réactiver le lien existant
        lien.is_active = True
        lien.prix_achat_pain = payload.prix_achat_pain or lien.prix_achat_pain
        lien.contact_local = payload.contact_local or lien.contact_local
    else:
        lien = LivreurBoulangerie(
            livreur_id=livreur.id,
            boulangerie_id=b.id,
            prix_achat_pain=payload.prix_achat_pain,
            contact_local=payload.contact_local,
        )
        db.add(lien)

    await db.commit()
    await db.refresh(lien)
    return _build_fournisseur_response(b, lien)


@router.put("/{boulangerie_id}/contrat", response_model=FournisseurResponse)
async def update_contrat(
    boulangerie_id: int,
    payload: FournisseurContratUpdate,
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour le contrat avec cette boulangerie (prix, contact local)."""
    result = await db.execute(
        select(Boulangerie, LivreurBoulangerie)
        .join(LivreurBoulangerie, LivreurBoulangerie.boulangerie_id == Boulangerie.id)
        .where(
            Boulangerie.id == boulangerie_id,
            LivreurBoulangerie.livreur_id == livreur.id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Boulangerie introuvable")
    b, lien = row

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(lien, field, value)
    db.add(lien)
    await db.commit()
    await db.refresh(lien)
    return _build_fournisseur_response(b, lien)


@router.delete("/{boulangerie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_fournisseur(
    boulangerie_id: int,
    livreur: Livreur = Depends(livreur_only()),
    db: AsyncSession = Depends(get_db),
):
    """Se délie de cette boulangerie fournisseur."""
    result = await db.execute(
        select(LivreurBoulangerie).where(
            LivreurBoulangerie.livreur_id == livreur.id,
            LivreurBoulangerie.boulangerie_id == boulangerie_id,
        )
    )
    lien = result.scalar_one_or_none()
    if not lien:
        raise HTTPException(status_code=404, detail="Lien introuvable")
    lien.is_active = False
    db.add(lien)
    await db.commit()
