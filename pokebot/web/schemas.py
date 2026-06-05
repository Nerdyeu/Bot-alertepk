"""Schemas d'entree (corps de requete) pour l'API web."""
from __future__ import annotations

from pydantic import BaseModel


class ProductIn(BaseModel):
    name: str
    set_code: str | None = None
    image_url: str | None = None
    reference_price: float | None = None
    reference_source: str = "manual"
    threshold_pct: float | None = None
    enabled: bool = True
    notes: str | None = None


class ProductReferenceIn(BaseModel):
    price: float


class LinkIn(BaseModel):
    shop_id: int
    direct_url: str | None = None
    search_query: str | None = None
    enabled: bool = True


class ShopIn(BaseModel):
    key: str
    name: str
    base_url: str
    adapter: str = "shopify"
    enabled: bool = True
    config: dict = {}
    note: str | None = None
