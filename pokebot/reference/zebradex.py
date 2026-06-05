"""Fournisseur 'zebradex' — cote de reference via la recherche publique ZebraDex.

Le site ZebraDex expose, pour sa propre barre de recherche, un endpoint JSON
PUBLIC et en LECTURE SEULE (utilise tel quel par les visiteurs non connectes) :

    GET {base}/include/search/autocomplete.php?q=...&lang=fr&type=sealed
    -> [{ "name", "code", "url", "image_url", "price", "ebay_url", ... }, ...]

`price` est la cote du produit scelle. On NE CONTOURNE AUCUNE authentification
ni captcha — c'est la donnee servie aux visiteurs non connectes.

NOTE robots.txt : cet endpoint est sous /include/, que le robots.txt de
ZebraDex interdit aux crawlers. Sur choix explicite de l'utilisateur
(ZEBRADEX_IGNORE_ROBOTS), on l'interroge tout de meme, mais UNIQUEMENT pour
ZebraDex, en LECTURE SEULE, 1x/jour max (cf. reference/service.py) et avec le
rate-limiting du client. Le scraping des boutiques, lui, respecte robots.txt.

Voies avancees (desactivees par defaut, sans contournement) :
  - ZEBRADEX_API_BASE : override si vous disposez d'une autre base d'API JSON.
  - Identifiants personnels : reserve a une lecture authentifiee conforme aux
    CGU, non implementee tant qu'un flux officiel n'est pas confirme.

En cas d'echec / produit introuvable, on retombe proprement sur la cote saisie
manuellement (reference_price).
"""
from __future__ import annotations

import re

from ..matching import best_match, strip_accents
from ..models import Product
from ..utils.http import HttpClient
from ..utils.logging import get_logger
from .base import ReferenceProvider, ReferenceResult

log = get_logger("zebradex")

_HEADERS = {"X-Requested-With": "XMLHttpRequest"}

# La recherche ZebraDex fait un ET sur les mots (insensible aux accents) : on lui
# envoie donc surtout les mots DISTINCTIFS (nom de l'extension) et on retire les
# mots generiques / grammaticaux + les apostrophes (qui cassent le ET).
_GENERIC = {
    "coffret", "dresseur", "elite", "etb", "bundle", "display", "booster", "boosters",
    "boite", "boites", "box", "pack", "paquet", "blister", "tin", "pokemon", "jcc", "tcg",
    "edition", "scelle", "scelles", "neuf", "fr", "ja", "francaise", "francais", "version",
    "de", "du", "des", "la", "le", "les", "un", "une", "et", "of", "the",
}
_SETCODE = re.compile(r"^[a-z]{2,3}\d{1,3}(?:[.\-]\d{1,2})?$")  # ex: me04, ev08


def _build_query(name: str) -> str:
    base = strip_accents(name).lower().replace("’", " ").replace("'", " ")
    base = re.sub(r"[^a-z0-9 ]+", " ", base)
    tokens = [t for t in base.split() if len(t) > 1]
    distinctive = [t for t in tokens if t not in _GENERIC and not _SETCODE.match(t)]
    return " ".join(distinctive) or " ".join(tokens)


_URL_SETCODE = re.compile(r"/([a-z]{1,3}\d{1,2}[a-z]?)/", re.I)


def _set_code_from_url(url: str | None) -> str | None:
    m = _URL_SETCODE.search(url or "")
    return m.group(1).upper() if m else None


def search_sealed(settings, query: str, limit: int = 15) -> list[dict]:
    """Recherche de produits SCELLES sur ZebraDex (pour l'ajout depuis l'UI).

    Renvoie une liste normalisee : name, code (type), set_code, url, image_url, price.
    Lecture seule, meme endpoint public que la cote.
    """
    base = (settings.zebradex_api_base or settings.zebradex_base).rstrip("/")
    http = HttpClient(settings)
    try:
        items = http.get_json(
            f"{base}/include/search/autocomplete.php",
            params={"q": query, "lang": settings.zebradex_lang, "type": "sealed"},
            headers=_HEADERS,
            ignore_robots=settings.zebradex_ignore_robots,
        )
    finally:
        http.close()

    results: list[dict] = []
    if isinstance(items, list):
        for it in items[:limit]:
            if not isinstance(it, dict):
                continue
            price = it.get("price")
            try:
                price = float(price) if price not in (None, "") else None
            except (TypeError, ValueError):
                price = None
            results.append({
                "name": it.get("name"),
                "code": it.get("code"),
                "set_code": _set_code_from_url(it.get("url")),
                "url": it.get("url"),
                "image_url": it.get("image_url"),
                "price": price,
            })
    return results


class ZebradexReferenceProvider(ReferenceProvider):
    name = "zebradex"

    def __init__(self, settings):
        super().__init__(settings)
        self._http: HttpClient | None = None

    def _client(self) -> HttpClient:
        # Client partage entre produits d'un meme cycle -> rate-limiting respecte.
        if self._http is None:
            self._http = HttpClient(self.settings)
        return self._http

    def get(self, product: Product) -> ReferenceResult:
        base = (self.settings.zebradex_api_base or self.settings.zebradex_base).rstrip("/")
        try:
            items = self._client().get_json(
                f"{base}/include/search/autocomplete.php",
                params={
                    "q": _build_query(product.name),
                    "lang": self.settings.zebradex_lang,
                    "type": "sealed",
                },
                headers=_HEADERS,
                ignore_robots=self.settings.zebradex_ignore_robots,
            )
            return self._pick(items, product)
        except Exception as exc:
            log.warning("ZebraDex indisponible (%s) — repli sur la cote manuelle", exc)
            return ReferenceResult(
                price=product.reference_price,
                source="manual" if product.reference_price else "zebradex",
                note=f"ZebraDex indisponible ({exc})",
            )

    def close(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    def _pick(self, items, product: Product) -> ReferenceResult:
        if not isinstance(items, list) or not items:
            return self._fallback(product, "aucun resultat ZebraDex")

        candidates = [(it.get("name", ""), it) for it in items if isinstance(it, dict)]
        best, sc = best_match(product.name, candidates, self.settings.match_min_score)
        if best is None or best.get("price") in (None, 0):
            return self._fallback(product, f"produit non trouve sur ZebraDex (meilleur score {sc:.0f})")

        try:
            price = float(best["price"])
        except (TypeError, ValueError):
            return self._fallback(product, "prix ZebraDex illisible")

        return ReferenceResult(
            price=price,
            source="zebradex",
            note=f"{best.get('name')} (match {sc:.0f})",
            image_url=best.get("image_url"),
            ref_url=best.get("url"),
        )

    def _fallback(self, product: Product, why: str) -> ReferenceResult:
        if product.reference_price:
            return ReferenceResult(
                price=product.reference_price, source="manual",
                note=f"{why} — cote manuelle utilisee",
            )
        return ReferenceResult(price=None, source="zebradex", note=why)
