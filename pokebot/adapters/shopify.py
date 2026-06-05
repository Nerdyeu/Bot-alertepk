"""Adaptateur Shopify : utilise les endpoints JSON structures plutot que le HTML.

Strategie (du plus fiable au moins fiable) :
  1. URL directe fournie -> GET /products/<handle>.json
  2. Recherche -> /search/suggest.json puis confirmation via /products/<handle>.json
  3. Repli -> pagination de /products.json (mise en cache pour le cycle)

La detection de page de "challenge" anti-bot est geree par le client HTTP.
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from ..core.stock import IN_STOCK, OUT_OF_STOCK
from ..matching import best_match
from ..models import Product, ProductShop
from ..utils.errors import NotFoundError, StructureError
from ..utils.logging import get_logger
from .base import ProductResult, ShopAdapter

log = get_logger("shopify")

_MAX_PAGES = 6  # repli products.json : 6 * 250 = 1500 produits max


class ShopifyAdapter(ShopAdapter):
    type = "shopify"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._all_products_cache: list[dict] | None = None

    # -- API publique de l'adaptateur --------------------------------------
    def fetch(self, product: Product, link: ProductShop | None) -> ProductResult:
        if link and link.direct_url:
            return self._from_direct_url(link.direct_url)
        query = (link.search_query if link and link.search_query else None) or product.name
        if product.set_code:
            query = f"{query} {product.set_code}"
        return self._search(query)

    # -- 1. URL directe -----------------------------------------------------
    def _from_direct_url(self, url: str) -> ProductResult:
        json_url = self._to_product_json_url(url)
        data = self.http.get_json(json_url)
        prod = data.get("product")
        if not prod:
            raise StructureError("produit absent du JSON Shopify")
        return self._parse_product(prod, page_url=self._strip_json(url), match_score=100.0)

    # -- 2. Recherche via suggest.json -------------------------------------
    def _search(self, query: str) -> ProductResult:
        try:
            data = self.http.get_json(
                f"{self.base}/search/suggest.json",
                params={
                    "q": query,
                    "resources[type]": "product",
                    "resources[limit]": 10,
                    "resources[options][unavailable_products]": "last",
                },
            )
            items = (
                data.get("resources", {}).get("results", {}).get("products", [])
            )
            candidates = [(it.get("title", ""), it) for it in items]
            best, sc = best_match(query, candidates, self.settings.match_min_score)
            if best is not None:
                return self._confirm_suggest(best, sc)
        except StructureError:
            # suggest.json indisponible -> on tente le repli products.json
            log.debug("suggest.json indisponible pour %s, repli products.json", self.base)

        return self._search_fallback(query)

    def _confirm_suggest(self, item: dict, score: float) -> ProductResult:
        handle = item.get("handle")
        page_url = self._abs(item.get("url"))
        if handle:
            try:
                data = self.http.get_json(f"{self.base}/products/{handle}.json")
                prod = data.get("product")
                if prod:
                    return self._parse_product(prod, page_url=page_url, match_score=score)
            except StructureError:
                pass  # on retombe sur les champs de suggest.json
        # Repli : champs bruts de suggest.json (prix en centimes)
        price = _to_float(item.get("price"))
        if price is not None and price > 1000:  # heuristique centimes
            price = price / 100.0
        available = item.get("available")
        return ProductResult(
            found=True,
            price=price,
            available=available,
            stock_status=IN_STOCK if available else OUT_OF_STOCK,
            url=page_url,
            title=item.get("title"),
            image_url=item.get("image"),
            match_score=score,
            raw=item,
        )

    # -- 3. Repli products.json --------------------------------------------
    def _search_fallback(self, query: str) -> ProductResult:
        products = self._load_all_products()
        candidates = [(p.get("title", ""), p) for p in products]
        best, sc = best_match(query, candidates, self.settings.match_min_score)
        if best is None:
            raise NotFoundError(f"aucune correspondance >= {self.settings.match_min_score} (score {sc})")
        return self._parse_product(best, page_url=f"{self.base}/products/{best.get('handle')}", match_score=sc)

    def _load_all_products(self) -> list[dict]:
        if self._all_products_cache is not None:
            return self._all_products_cache
        all_products: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            data = self.http.get_json(
                f"{self.base}/products.json", params={"limit": 250, "page": page}
            )
            chunk = data.get("products", [])
            if not chunk:
                break
            all_products.extend(chunk)
            if len(chunk) < 250:
                break
        self._all_products_cache = all_products
        return all_products

    # -- parsing ------------------------------------------------------------
    def _parse_product(
        self, prod: dict, page_url: str | None, match_score: float
    ) -> ProductResult:
        variants = prod.get("variants", []) or []
        available_variants = [v for v in variants if v.get("available")]
        usable = available_variants or variants
        prices = [
            _to_float(v.get("price")) for v in usable if _to_float(v.get("price")) is not None
        ]
        price = min(prices) if prices else None
        available = any(v.get("available") for v in variants)
        images = prod.get("images", []) or []
        image_url = None
        if images:
            first = images[0]
            image_url = first.get("src") if isinstance(first, dict) else first
        handle = prod.get("handle")
        url = page_url or (f"{self.base}/products/{handle}" if handle else self.base)
        return ProductResult(
            found=True,
            price=price,
            currency="EUR",
            available=available,
            stock_status=IN_STOCK if available else OUT_OF_STOCK,
            url=url,
            title=prod.get("title"),
            image_url=image_url,
            match_score=match_score,
            raw={"handle": handle},
        )

    # -- helpers URL --------------------------------------------------------
    def _abs(self, rel: str | None) -> str | None:
        if not rel:
            return None
        if rel.startswith("http"):
            return rel
        return f"{self.base}{rel}"

    def _strip_json(self, url: str) -> str:
        return url[:-5] if url.endswith(".json") else url

    def _to_product_json_url(self, url: str) -> str:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        path = parsed.path
        if path.endswith(".json"):
            clean_path = path
        elif "/products/" in path:
            handle = path.split("/products/")[1].split("/")[0]
            clean_path = f"/products/{handle}.json"
        else:
            clean_path = path.rstrip("/") + ".json"
        return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None
