"""Donnees initiales.

Les boutiques ne sont PLUS pre-remplies : l'utilisateur ajoute ses sites
lui-meme depuis l'onglet Sites (nom + URL + maniere de rechercher + statut).
On insere seulement un produit d'exemple pour ne pas avoir une UI vide.
"""
from __future__ import annotations

from sqlalchemy import select

from .database import session_scope
from .models import Product
from .utils.logging import get_logger

log = get_logger("seed")

EXAMPLE_PRODUCT = {
    "name": "ETB Chaos Ascendant ME04",
    "set_code": "ME04",
    "reference_price": None,
    "threshold_pct": None,
    "enabled": True,
    "notes": "Produit d'exemple — la cote ZebraDex se remplit au prochain scan.",
}


def seed_defaults() -> None:
    with session_scope() as db:
        if db.scalars(select(Product).limit(1)).first() is None:
            db.add(Product(**EXAMPLE_PRODUCT))
            log.info("Produit d'exemple insere.")
