"""Fournisseur 'manual' : la cote est saisie/mise a jour dans l'interface.

C'est l'option par defaut : zero risque vis-a-vis des CGU de ZebraDex, et
toujours fonctionnelle. Vous reportez la cote ZebraDex du jour dans l'UI.
"""
from __future__ import annotations

from ..models import Product
from .base import ReferenceProvider, ReferenceResult


class ManualReferenceProvider(ReferenceProvider):
    name = "manual"

    def get(self, product: Product) -> ReferenceResult:
        return ReferenceResult(
            price=product.reference_price,
            source="manual",
            note="" if product.reference_price else "aucune cote saisie",
        )
