"""Exceptions metier des adaptateurs, pour un rapport d'echec clair."""
from __future__ import annotations


class AdapterError(Exception):
    """Erreur generique d'un adaptateur (message lisible pour le rapport)."""


class ChallengeError(AdapterError):
    """Le site renvoie une page de verification / protection anti-bot."""


class BlockedError(AdapterError):
    """Acces refuse (403, robots.txt, IP bloquee)."""


class NotFoundError(AdapterError):
    """Produit introuvable sur la boutique."""


class StructureError(AdapterError):
    """La structure de la page/API a change (parsing impossible)."""
