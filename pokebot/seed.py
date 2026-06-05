"""Donnees initiales : boutiques de depart + un produit d'exemple.

Les boutiques Shopify sont activees ; les autres sont presentes mais
desactivees, pretes a etre configurees (selecteurs HTML) ou laissees telles
quelles (sites bloques / API officielle requise).
"""
from __future__ import annotations

from sqlalchemy import select

from .database import session_scope
from .models import Product, Shop
from .utils.logging import get_logger

log = get_logger("seed")

DEFAULT_SHOPS: list[dict] = [
    # --- Boutiques Shopify (endpoints JSON) : supportables ---
    {"key": "pokestation", "name": "PokeStation", "base_url": "https://pokestation.fr",
     "adapter": "shopify", "enabled": True},
    {"key": "monpokestore", "name": "Monpokestore", "base_url": "https://monpokestore.fr",
     "adapter": "shopify", "enabled": True},
    {"key": "fuji-store", "name": "Fuji Store", "base_url": "https://www.fuji-store.fr",
     "adapter": "shopify", "enabled": True},
    {"key": "blazingtail", "name": "Blazing Tail", "base_url": "https://www.blazingtail.fr",
     "adapter": "shopify", "enabled": True},
    {"key": "hikaru", "name": "Hikaru Distribution", "base_url": "https://hikarudistribution.com",
     "adapter": "shopify", "enabled": True},
    {"key": "arakemon", "name": "Arakemon", "base_url": "https://www.arakemon.com",
     "adapter": "shopify", "enabled": True},

    # --- A configurer (non Shopify) : adaptateur HTML + selecteurs CSS ---
    {"key": "magicbazar", "name": "Magic Bazar", "base_url": "https://www.magic-bazar.fr",
     "adapter": "html", "enabled": False,
     "config": {"search_url": "https://www.magic-bazar.fr/recherche?controller=search&s={query}",
                "result_link_selector": "a.product-thumbnail, a.thumbnail",
                "price_selector": "span.price, .current-price span",
                "availability_selector": "#product-availability, .product-availability"},
     "note": "Verifier/ajuster les selecteurs CSS avant activation."},
    {"key": "cartamania", "name": "Cartamania", "base_url": "https://www.cartamania.fr",
     "adapter": "html", "enabled": False,
     "config": {"search_url": "https://www.cartamania.fr/recherche?controller=search&s={query}"},
     "note": "Renseigner result_link_selector / price_selector."},
    {"key": "ludifolie", "name": "Ludifolie", "base_url": "https://www.ludifolie.com",
     "adapter": "html", "enabled": False, "config": {},
     "note": "Renseigner la config HTML (search_url, selecteurs)."},
    {"key": "otakumanga", "name": "Otaku Manga", "base_url": "https://www.otakumanga.fr",
     "adapter": "html", "enabled": False, "config": {},
     "note": "Renseigner la config HTML (search_url, selecteurs)."},

    # --- Bloques proprement (protection anti-bot / API officielle requise) ---
    {"key": "fnac", "name": "Fnac", "base_url": "https://www.fnac.com", "adapter": "blocked",
     "enabled": False, "config": {"reason": "protection anti-bot ; pas d'acces propre sans API"}},
    {"key": "cultura", "name": "Cultura", "base_url": "https://www.cultura.com", "adapter": "blocked",
     "enabled": False, "config": {"reason": "protection anti-bot ; pas d'acces propre sans API"}},
    {"key": "amazon", "name": "Amazon", "base_url": "https://www.amazon.fr", "adapter": "blocked",
     "enabled": False, "config": {"reason": "files d'attente/anti-bot ; API SP officielle requise"}},
    {"key": "micromania", "name": "Micromania", "base_url": "https://www.micromania.fr",
     "adapter": "blocked", "enabled": False,
     "config": {"reason": "protection anti-bot ; pas d'acces propre sans API"}},
    {"key": "cardmarket", "name": "Cardmarket", "base_url": "https://www.cardmarket.com",
     "adapter": "blocked", "enabled": False,
     "config": {"reason": "API Cardmarket officielle (OAuth) requise — voir README"}},
    {"key": "ebay", "name": "eBay", "base_url": "https://www.ebay.fr", "adapter": "blocked",
     "enabled": False, "config": {"reason": "API eBay Browse officielle (cle) requise — voir README"}},
]

EXAMPLE_PRODUCT = {
    "name": "ETB Chaos Ascendant ME04",
    "set_code": "ME04",
    "reference_price": None,
    "threshold_pct": None,
    "enabled": True,
    "notes": "Produit d'exemple — saisissez la cote ZebraDex puis lancez un scan.",
}


def seed_defaults() -> None:
    with session_scope() as db:
        if db.scalars(select(Shop).limit(1)).first() is None:
            for data in DEFAULT_SHOPS:
                db.add(Shop(**data))
            log.info("Boutiques par defaut inserees (%s).", len(DEFAULT_SHOPS))
        if db.scalars(select(Product).limit(1)).first() is None:
            db.add(Product(**EXAMPLE_PRODUCT))
            log.info("Produit d'exemple insere.")
