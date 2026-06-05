"""Service de cote : choix du fournisseur, rafraichissement quotidien,
et historisation pour le graphique (source = ZebraDex uniquement)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, settings as default_settings
from ..models import Product, ReferencePoint, utcnow
from ..utils.logging import get_logger
from .base import ReferenceProvider
from .manual import ManualReferenceProvider
from .zebradex import ZebradexReferenceProvider

log = get_logger("reference")


def get_provider(settings: Settings = default_settings) -> ReferenceProvider:
    if settings.reference_provider == "zebradex":
        return ZebradexReferenceProvider(settings)
    return ManualReferenceProvider(settings)


def _last_point(db: Session, product_id: int) -> ReferencePoint | None:
    return db.scalars(
        select(ReferencePoint)
        .where(ReferencePoint.product_id == product_id)
        .order_by(ReferencePoint.recorded_at.desc())
        .limit(1)
    ).first()


def refresh_reference(
    db: Session, product: Product, provider: ReferenceProvider, settings: Settings = default_settings
) -> float | None:
    """Met a jour la cote du produit (au plus 1x / REFERENCE_REFRESH_HOURS) et
    enregistre un point d'historique si la valeur a change.

    Renvoie la cote courante utilisable pour le calcul d'ecart.
    """
    now = utcnow()
    refresh_delta = dt.timedelta(hours=settings.reference_refresh_hours)
    needs_fetch = (
        provider.name != "manual"
        and (product.reference_updated_at is None or now - product.reference_updated_at >= refresh_delta)
    )

    if needs_fetch:
        result = provider.get(product)
        if result.price is not None:
            product.reference_price = result.price
            product.reference_source = result.source
            product.reference_updated_at = now
            # On complete l'image du produit si absente (confirmation par image)
            if result.image_url and not product.image_url:
                product.image_url = result.image_url
            db.add(product)
        if result.note:
            log.info("Cote %s [%s]: %s", product.name, result.source, result.note)

    current = product.reference_price
    if current is not None:
        last = _last_point(db, product.id)
        changed = last is None or abs(last.price - current) > 1e-9
        recent = last is not None and (now - last.recorded_at) < dt.timedelta(hours=12)
        if changed or not recent:
            if last is None or changed:
                db.add(
                    ReferencePoint(
                        product_id=product.id,
                        price=current,
                        source=product.reference_source,
                        recorded_at=now,
                    )
                )
    return current
