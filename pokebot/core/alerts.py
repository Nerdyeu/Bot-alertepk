"""Decision d'alerte : seuil (global ou par produit), stock, et anti-spam."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Alert, Product, Shop, utcnow
from .stock import IN_STOCK


@dataclass
class AlertDecision:
    should_alert: bool
    discount_pct: float | None
    reason: str


def compute_discount(reference_price: float, price: float) -> float:
    return (reference_price - price) / reference_price * 100.0


def threshold_for(product: Product, settings: Settings) -> float:
    return product.threshold_pct if product.threshold_pct is not None else settings.global_threshold_pct


def signature(product_id: int, shop_id: int) -> str:
    return f"{product_id}:{shop_id}"


def evaluate(
    db: Session,
    product: Product,
    shop: Shop,
    price: float | None,
    stock_status: str,
    reference_price: float | None,
    settings: Settings,
    confident: bool = True,
) -> AlertDecision:
    if reference_price is None or reference_price <= 0:
        return AlertDecision(False, None, "pas de cote de reference")
    if price is None:
        return AlertDecision(False, None, "prix introuvable")

    discount = compute_discount(reference_price, price)
    threshold = threshold_for(product, settings)
    if discount < threshold:
        return AlertDecision(False, discount, f"sous le seuil ({discount:.1f}% < {threshold:.0f}%)")
    if not confident:
        return AlertDecision(False, discount, "correspondance peu fiable (image/nom)")
    if settings.enable_stock_filter and stock_status != IN_STOCK:
        return AlertDecision(False, discount, f"stock non confirme ({stock_status})")

    last = db.scalars(
        select(Alert)
        .where(Alert.signature == signature(product.id, shop.id))
        .order_by(Alert.sent_at.desc())
        .limit(1)
    ).first()
    if last is not None:
        improved = price <= last.price * (1 - settings.alert_min_price_drop_pct / 100.0)
        cooled = (utcnow() - last.sent_at) >= dt.timedelta(hours=settings.alert_cooldown_hours)
        if not (improved or cooled):
            return AlertDecision(False, discount, "deja alerte (anti-spam, prix/stock stables)")

    return AlertDecision(True, discount, "alerte declenchee")
