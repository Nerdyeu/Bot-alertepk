"""Conversion modeles -> dictionnaires JSON pour l'API."""
from __future__ import annotations

from ..config import Settings
from ..core.alerts import threshold_for
from ..core.stock import IN_STOCK
from ..models import Observation, Product, ProductShop, Shop


def _iso(value):
    return value.isoformat() if value else None


def link_to_dict(link: ProductShop) -> dict:
    return {
        "id": link.id,
        "shop_id": link.shop_id,
        "direct_url": link.direct_url,
        "search_query": link.search_query,
        "enabled": link.enabled,
    }


def product_to_dict(product: Product, settings: Settings) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "set_code": product.set_code,
        "image_url": product.image_url,
        "reference_price": product.reference_price,
        "reference_source": product.reference_source,
        "reference_updated_at": _iso(product.reference_updated_at),
        "threshold_pct": product.threshold_pct,
        "effective_threshold": threshold_for(product, settings),
        "enabled": product.enabled,
        "notes": product.notes,
        "links": [link_to_dict(link) for link in product.links],
    }


def shop_to_dict(shop: Shop) -> dict:
    from ..search_methods import label_of

    return {
        "id": shop.id,
        "key": shop.key,
        "name": shop.name,
        "base_url": shop.base_url,
        "search_method": shop.search_method,
        "method_label": label_of(shop.search_method),
        "adapter": shop.adapter,
        "enabled": shop.enabled,
        "config": shop.config or {},
        "note": shop.note,
    }


def observation_to_dict(
    obs: Observation, product: Product | None, shop: Shop | None, settings: Settings
) -> dict:
    threshold = threshold_for(product, settings) if product else settings.global_threshold_pct
    is_alert = (
        obs.ok
        and obs.found
        and obs.discount_pct is not None
        and obs.discount_pct >= threshold
        and (not settings.enable_stock_filter or obs.stock_status == IN_STOCK)
    )
    return {
        "product_id": obs.product_id,
        "product_name": product.name if product else f"#{obs.product_id}",
        "set_code": product.set_code if product else None,
        "shop_id": obs.shop_id,
        "shop_name": shop.name if shop else f"#{obs.shop_id}",
        "ok": obs.ok,
        "found": obs.found,
        "error": obs.error,
        "price": obs.price,
        "currency": obs.currency,
        "reference_price": obs.reference_price,
        "discount_pct": round(obs.discount_pct, 1) if obs.discount_pct is not None else None,
        "threshold": threshold,
        "available": obs.available,
        "stock_status": obs.stock_status,
        "url": obs.url,
        "title": obs.title,
        "match_score": obs.match_score,
        "image_match_score": obs.image_match_score,
        "alerted": obs.alerted,
        "is_alert": is_alert,
        "checked_at": _iso(obs.checked_at),
    }
