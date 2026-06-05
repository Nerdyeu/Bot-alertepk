"""Interface des fournisseurs de prix de reference (la "cote")."""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..models import Product


@dataclass
class ReferenceResult:
    price: float | None
    source: str
    note: str = ""


class ReferenceProvider:
    name: str = "base"

    def __init__(self, settings: Settings):
        self.settings = settings

    def get(self, product: Product) -> ReferenceResult:  # pragma: no cover
        raise NotImplementedError
