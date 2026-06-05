"""Interface commune des adaptateurs de boutique.

Ajouter une boutique = ajouter un adaptateur implementant `fetch()`, sans
toucher au reste du code. La logique de scan ne connait que `ProductResult`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Settings
from ..core.stock import UNKNOWN
from ..models import Product, ProductShop, Shop
from ..utils.http import HttpClient


@dataclass
class ProductResult:
    """Resultat normalise d'une recherche produit sur une boutique."""

    found: bool = False
    price: float | None = None
    currency: str = "EUR"
    available: bool | None = None
    stock_status: str = UNKNOWN
    url: str | None = None
    title: str | None = None
    image_url: str | None = None
    match_score: float | None = None
    raw: dict = field(default_factory=dict)

    @classmethod
    def not_found(cls, score: float | None = None) -> "ProductResult":
        return cls(found=False, match_score=score)


class ShopAdapter:
    """Classe de base. Les adaptateurs concrets surchargent `fetch()`."""

    type: str = "base"

    def __init__(self, shop: Shop, http: HttpClient, settings: Settings):
        self.shop = shop
        self.http = http
        self.settings = settings
        self.config: dict = shop.config or {}
        self.base = shop.base_url.rstrip("/")

    def fetch(self, product: Product, link: ProductShop | None) -> ProductResult:
        raise NotImplementedError
