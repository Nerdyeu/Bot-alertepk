"""Adaptateur HTML generique, pilote par des selecteurs CSS dans la config.

A utiliser pour les boutiques NON Shopify. La config (JSON de la boutique)
attend par ex. :

    {
      "search_url": "https://exemple.fr/recherche?controller=search&s={query}",
      "result_link_selector": "a.product-thumbnail",
      "price_selector": "span.price",
      "availability_selector": "span.product-availability",
      "image_selector": "img.product-cover",
      "currency": "EUR"
    }
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from ..core import stock as stockmod
from ..matching import best_match
from ..models import Product, ProductShop
from ..utils.errors import NotFoundError, StructureError
from .base import ProductResult, ShopAdapter

_PRICE_RE = re.compile(r"(\d{1,4}(?:[.\s]\d{3})*(?:[.,]\d{1,2})?)")


class HtmlAdapter(ShopAdapter):
    type = "html"

    def fetch(self, product: Product, link: ProductShop | None) -> ProductResult:
        if link and link.direct_url:
            return self._parse_product_page(link.direct_url, match_score=100.0)
        query = (link.search_query if link and link.search_query else None) or product.name
        return self._search(query, product)

    def _search(self, query: str, product: Product) -> ProductResult:
        template = self.config.get("search_url")
        if not template:
            raise StructureError("config 'search_url' manquante pour cet adaptateur HTML")
        url = template.format(query=quote_plus(query))
        resp = self.http.get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        selector = self.config.get("result_link_selector", "a")
        candidates: list[tuple[str, dict]] = []
        for a in soup.select(selector):
            href = a.get("href")
            title = a.get("title") or a.get_text(" ", strip=True)
            if href and title:
                candidates.append((title, {"href": urljoin(url, href), "title": title}))
        best, sc = best_match(query, candidates, self.settings.match_min_score)
        if best is None:
            raise NotFoundError(f"aucune correspondance sur la page de recherche (score {sc})")
        return self._parse_product_page(best["href"], match_score=sc)

    def _parse_product_page(self, url: str, match_score: float) -> ProductResult:
        resp = self.http.get(url)
        soup = BeautifulSoup(resp.text, "lxml")

        price = self._extract_price(soup)
        title = self._extract_text(soup, self.config.get("title_selector")) or (
            soup.title.get_text(strip=True) if soup.title else None
        )
        avail_text = self._extract_text(soup, self.config.get("availability_selector"))
        # Si pas de selecteur de dispo, on classe sur tout le texte visible.
        stock_status = stockmod.classify(avail_text or soup.get_text(" ", strip=True)[:5000])
        image_url = self._extract_image(soup, url)

        return ProductResult(
            found=price is not None,
            price=price,
            currency=self.config.get("currency", "EUR"),
            available=(stock_status == stockmod.IN_STOCK),
            stock_status=stock_status,
            url=url,
            title=title,
            image_url=image_url,
            match_score=match_score,
        )

    # -- helpers ------------------------------------------------------------
    def _extract_text(self, soup: BeautifulSoup, selector: str | None) -> str | None:
        if not selector:
            return None
        el = soup.select_one(selector)
        return el.get_text(" ", strip=True) if el else None

    def _extract_price(self, soup: BeautifulSoup) -> float | None:
        selector = self.config.get("price_selector")
        text = None
        if selector:
            el = soup.select_one(selector)
            if el:
                text = el.get("content") or el.get_text(" ", strip=True)
        if not text:
            # repli : balise meta Open Graph / schema.org
            meta = soup.select_one('meta[property="product:price:amount"], meta[itemprop="price"]')
            if meta:
                text = meta.get("content")
        if not text:
            return None
        match = _PRICE_RE.search(text)
        if not match:
            return None
        raw = match.group(1).replace(" ", "").replace(" ", "")
        # "1.299,99" -> "1299.99" ; "12,99" -> "12.99"
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None

    def _extract_image(self, soup: BeautifulSoup, base_url: str) -> str | None:
        selector = self.config.get("image_selector")
        if selector:
            el = soup.select_one(selector)
            if el:
                src = el.get("src") or el.get("data-src") or el.get("content")
                if src:
                    return urljoin(base_url, src)
        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            return urljoin(base_url, og["content"])
        return None
