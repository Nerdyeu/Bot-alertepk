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
    image_url: str | None = None  # image ZebraDex (sert a la confirmation par image)
    ref_url: str | None = None  # URL de la fiche ZebraDex correspondante


class ReferenceProvider:
    name: str = "base"

    def __init__(self, settings: Settings):
        self.settings = settings

    def get(self, product: Product) -> ReferenceResult:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:
        """Libere les ressources eventuelles (ex: client HTTP). No-op par defaut."""
