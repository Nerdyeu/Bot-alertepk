"""Registre des adaptateurs : type (str) -> classe.

Ajouter une boutique d'un nouveau type = enregistrer une classe ici.
"""
from __future__ import annotations

from ..config import Settings
from ..models import Shop
from ..utils.http import HttpClient
from .base import ShopAdapter
from .blocked import BlockedAdapter
from .ebay import EbayAdapter
from .html import HtmlAdapter
from .shopify import ShopifyAdapter

_REGISTRY: dict[str, type[ShopAdapter]] = {
    ShopifyAdapter.type: ShopifyAdapter,
    HtmlAdapter.type: HtmlAdapter,
    EbayAdapter.type: EbayAdapter,
    BlockedAdapter.type: BlockedAdapter,
}


def list_adapter_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def build_adapter(shop: Shop, http: HttpClient, settings: Settings) -> ShopAdapter | None:
    cls = _REGISTRY.get(shop.adapter)
    if cls is None:
        return None
    return cls(shop, http, settings)
