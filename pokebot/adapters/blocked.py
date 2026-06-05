"""Adaptateur 'blocked' : pour les sites volontairement non supportes en scraping
(protections anti-bot agressives, CGU strictes, ou API officielle requise).

Il ne tente AUCUN contournement : il signale proprement un echec explicite,
ce qui les fait apparaitre dans le rapport des sites en echec.
Voir README pour les voies propres (API eBay Browse, API Cardmarket, etc.).
"""
from __future__ import annotations

from ..models import Product, ProductShop
from ..utils.errors import BlockedError
from .base import ProductResult, ShopAdapter


class BlockedAdapter(ShopAdapter):
    type = "blocked"

    def fetch(self, product: Product, link: ProductShop | None) -> ProductResult:
        reason = self.config.get(
            "reason",
            "site non supporte proprement (protection anti-bot / API officielle requise)",
        )
        raise BlockedError(reason)
