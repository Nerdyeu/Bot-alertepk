"""Classification du statut de stock a partir de texte libre.

Gere le cas des "files d'attente" / waiting rooms (type drops) : on ne veut
PAS declencher une vraie alerte d'achat quand il faut en realite une
invitation ou patienter dans une file -> statut "uncertain".
"""
from __future__ import annotations

# Statuts possibles
IN_STOCK = "in_stock"
OUT_OF_STOCK = "out_of_stock"
UNCERTAIN = "uncertain"  # stock incertain (file d'attente, precommande, drop...)
UNKNOWN = "unknown"

_WAITING_ROOM = (
    "file d attente",
    "file d'attente",
    "salle d attente",
    "waiting room",
    "virtual queue",
    "queue-it",
    "vous etes dans la file",
    "patientez",
    "sur invitation",
    "invitation",
    "acces anticipe",
    "drop",
    "vente flash a venir",
    "bientot disponible",
    "coming soon",
)
_PREORDER = (
    "precommande",
    "pre-commande",
    "pre commande",
    "pre-order",
    "preorder",
    "sortie le",
    "disponible le",
)
_OUT = (
    "rupture",
    "epuise",
    "indisponible",
    "sold out",
    "out of stock",
    "victime de son succes",
    "stock epuise",
    "non disponible",
)
_IN = (
    "en stock",
    "disponible",
    "ajouter au panier",
    "add to cart",
    "in stock",
    "expedie sous",
)


def _norm(text: str) -> str:
    import unicodedata

    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return text.lower()


def classify(text: str | None) -> str:
    """Devine le statut de stock depuis un texte de page produit."""
    if not text:
        return UNKNOWN
    t = _norm(text)
    if any(k in t for k in _WAITING_ROOM) or any(k in t for k in _PREORDER):
        return UNCERTAIN
    if any(k in t for k in _OUT):
        return OUT_OF_STOCK
    if any(k in t for k in _IN):
        return IN_STOCK
    return UNKNOWN
