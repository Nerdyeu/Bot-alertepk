"""Adaptateur eBay via l'API officielle Browse (voie propre, autorisee).

Aucun scraping : on utilise l'API publique d'eBay avec vos identifiants
developpeur (gratuits). Flux OAuth2 "client credentials" (token applicatif),
puis recherche d'annonces. Le marche secondaire est ainsi couvert legalement.

Config .env : EBAY_CLIENT_ID, EBAY_CLIENT_SECRET (et EBAY_MARKETPLACE_ID).
Config boutique (JSON), optionnelle :
  - "filter" : filtre Browse (defaut "buyingOptions:{FIXED_PRICE}" = achat immediat ;
               ex. neuf seulement : "buyingOptions:{FIXED_PRICE},conditionIds:{1000}")
  - "marketplace_id" : ex. "EBAY_FR"
"""
from __future__ import annotations

import base64
import threading
import time

import httpx

from ..core.stock import IN_STOCK
from ..matching import score
from ..models import Product, ProductShop
from ..utils.errors import BlockedError, NotFoundError, StructureError
from ..utils.logging import get_logger
from .base import ProductResult, ShopAdapter

log = get_logger("ebay")

_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
_SCOPE = "https://api.ebay.com/oauth/api_scope"

_token_cache: dict[str, tuple[str, float]] = {}  # client_id -> (token, expiry_ts)
_token_lock = threading.Lock()


def _get_token(client_id: str, secret: str, timeout: float) -> str:
    with _token_lock:
        cached = _token_cache.get(client_id)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
        resp = httpx.post(
            _TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": _SCOPE},
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise BlockedError(f"authentification eBay refusee (HTTP {resp.status_code})")
        payload = resp.json()
        token = payload["access_token"]
        _token_cache[client_id] = (token, time.time() + payload.get("expires_in", 7200))
        return token


class EbayAdapter(ShopAdapter):
    type = "ebay"

    def fetch(self, product: Product, link: ProductShop | None) -> ProductResult:
        cid = self.settings.ebay_client_id
        secret = self.settings.ebay_client_secret
        if not (cid and secret):
            raise BlockedError("identifiants API eBay manquants (EBAY_CLIENT_ID/SECRET dans .env)")

        token = _get_token(cid, secret, self.settings.request_timeout)
        query = (link.search_query if link and link.search_query else None) or product.name
        if product.set_code:
            query = f"{query} {product.set_code}"

        params = {"q": query, "limit": 25, "sort": "price"}
        filt = self.config.get("filter", "buyingOptions:{FIXED_PRICE}")
        if filt:
            params["filter"] = filt
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.config.get("marketplace_id")
            or self.settings.ebay_marketplace_id,
        }
        # API officielle authentifiee : robots.txt (destine aux crawlers web) ne
        # s'applique pas ; on conserve le rate-limiting du client.
        data = self.http.get_json(
            f"{self.base}/buy/browse/v1/item_summary/search",
            params=params,
            headers=headers,
            ignore_robots=True,
        )
        items = data.get("itemSummaries") or []
        if not items:
            raise NotFoundError("aucune annonce eBay pour cette recherche")

        # Items tries par prix croissant : on renvoie la 1re annonce qui matche bien
        # (= la moins chere au-dessus du seuil de correspondance).
        for item in items:
            title = item.get("title", "")
            sc = score(query, title)
            if sc >= self.settings.match_min_score:
                return self._to_result(item, sc)
        raise NotFoundError(
            f"annonces eBay trouvees mais aucune ne correspond assez (seuil {self.settings.match_min_score})"
        )

    def _to_result(self, item: dict, match_score: float) -> ProductResult:
        price_block = item.get("price") or {}
        try:
            price = float(price_block.get("value"))
        except (TypeError, ValueError):
            raise StructureError("prix eBay illisible")
        condition = item.get("condition")
        title = item.get("title")
        image = (item.get("image") or {}).get("imageUrl")
        return ProductResult(
            found=True,
            price=price,
            currency=price_block.get("currency", "EUR"),
            available=True,
            stock_status=IN_STOCK,
            url=item.get("itemWebUrl"),
            title=f"{title} — {condition}" if condition else title,
            image_url=image,
            match_score=match_score,
            raw={"condition": condition, "note": "prix hors frais de port"},
        )
