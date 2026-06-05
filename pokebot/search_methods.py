"""Catalogue des « manieres de rechercher » proposees a l'utilisateur.

Chaque methode masque la technique (adaptateur + config) derriere un libelle
clair. Choisir une methode dans l'UI suffit ; on en derive l'adaptateur et la
config automatiquement.
"""
from __future__ import annotations

# Ordre = ordre d'affichage dans le menu deroulant.
SEARCH_METHODS = [
    {
        "key": "shopify",
        "label": "Shopify — recherche auto par nom",
        "adapter": "shopify",
        "needs_keys": False,
        "description": (
            "Le bot trouve les produits par leur nom, tout seul. "
            "Marche pour la plupart des boutiques Pokémon FR (PokéStation, Fuji, Hikaru…)."
        ),
    },
    {
        "key": "prestashop",
        "label": "PrestaShop — recherche par nom",
        "adapter": "html",
        "needs_keys": False,
        "description": (
            "Pour les boutiques PrestaShop. Recherche par nom "
            "(⚠️ certains sites bloquent la recherche automatique)."
        ),
    },
    {
        "key": "page_produit",
        "label": "Lien direct par produit",
        "adapter": "html",
        "needs_keys": False,
        "description": (
            "Tu colles le lien de chaque produit ; le bot y lit le prix. "
            "Marche sur beaucoup de sites, mais demande un lien par produit."
        ),
    },
    {
        "key": "ebay",
        "label": "eBay — annonces (API officielle)",
        "adapter": "ebay",
        "needs_keys": True,
        "description": (
            "Annonces eBay (neuf + occasion) via l'API officielle. "
            "Nécessite une clé eBay gratuite (réglages .env)."
        ),
    },
    {
        "key": "none",
        "label": "Aucune (juste lister le site)",
        "adapter": "blocked",
        "needs_keys": False,
        "description": (
            "Le bot ne cherche pas ici. Le site est seulement listé "
            "(utile pour un site protégé ou à surveiller à la main)."
        ),
    },
]

_BY_KEY = {m["key"]: m for m in SEARCH_METHODS}
DEFAULT_METHOD = "shopify"


def catalog() -> list[dict]:
    """Liste publique (pour l'API/UI) sans les détails internes."""
    return [
        {"key": m["key"], "label": m["label"], "description": m["description"],
         "needs_keys": m["needs_keys"]}
        for m in SEARCH_METHODS
    ]


def label_of(method_key: str) -> str:
    m = _BY_KEY.get(method_key)
    return m["label"] if m else method_key


def adapter_for(method_key: str) -> str:
    m = _BY_KEY.get(method_key, _BY_KEY[DEFAULT_METHOD])
    return m["adapter"]


def build(method_key: str, base_url: str) -> tuple[str, dict]:
    """Renvoie (adapter, config) pour une méthode + une URL de base."""
    base = (base_url or "").rstrip("/")
    if method_key == "prestashop":
        config = {
            "search_url": base + "/recherche?controller=search&s={query}",
            "result_link_selector": ".product-title a, a.product-thumbnail, .product-name a, .thumbnail",
            "price_selector": "[itemprop=price]",
            "availability_selector": ".product-quantities, #product-availability",
        }
    elif method_key == "page_produit":
        config = {
            "price_selector": "[itemprop=price], meta[itemprop=price], .current-price, .price",
            "availability_selector": (
                "[itemprop=availability], .product-quantities, #product-availability, "
                ".product-availability, .stock"
            ),
        }
    elif method_key == "ebay":
        config = {"filter": "buyingOptions:{FIXED_PRICE}", "marketplace_id": "EBAY_FR"}
    elif method_key == "none":
        config = {"reason": "site non géré automatiquement (seulement listé)"}
    else:  # shopify (defaut)
        config = {}
    return adapter_for(method_key), config
