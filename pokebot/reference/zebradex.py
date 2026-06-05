"""Fournisseur 'zebradex' — branchement propre vers la cote ZebraDex.

IMPORTANT (respect des CGU) :
  - ZebraDex n'expose pas (a ce jour) d'API publique documentee, et la plupart
    des prix sont derriere un compte. Ce module NE CONTOURNE AUCUNE protection.
  - Deux voies propres sont prevues, desactivees par defaut :
      (a) ZEBRADEX_API_BASE : si vous disposez d'un point d'acces JSON
          legitime (ex. une API d'app officielle), on l'interroge en lecture.
      (b) Identifiants personnels (ZEBRADEX_EMAIL/PASSWORD) : reserve a une
          lecture authentifiee avec VOS identifiants, dans le respect des CGU.
          Non implemente tant qu'un flux officiel/autorise n'est pas confirme.

  En l'absence de l'un ou l'autre, ce fournisseur renvoie None : on retombe
  alors proprement sur la cote saisie manuellement (reference_price).
"""
from __future__ import annotations

from ..models import Product
from ..utils.http import HttpClient
from ..utils.logging import get_logger
from .base import ReferenceProvider, ReferenceResult

log = get_logger("zebradex")


class ZebradexReferenceProvider(ReferenceProvider):
    name = "zebradex"

    def get(self, product: Product) -> ReferenceResult:
        api_base = self.settings.zebradex_api_base
        if api_base:
            try:
                return self._from_api(api_base, product)
            except Exception as exc:  # repli sur la valeur manuelle
                log.warning("ZebraDex API indisponible (%s) — repli sur la cote manuelle", exc)

        if self.settings.zebradex_email and self.settings.zebradex_password:
            # Voie (b) : lecture authentifiee avec les identifiants de l'utilisateur.
            # Volontairement non implementee tant qu'un flux officiel/autorise
            # n'est pas confirme — aucun contournement de protection ici.
            log.info(
                "Lecture authentifiee ZebraDex non activee (aucun flux officiel confirme). "
                "Utilisation de la cote manuelle."
            )

        return ReferenceResult(
            price=product.reference_price,
            source="manual" if product.reference_price else "zebradex",
            note="cote ZebraDex non recuperee automatiquement (voir README) — valeur manuelle utilisee",
        )

    def _from_api(self, api_base: str, product: Product) -> ReferenceResult:
        """Lecture lecture-seule d'une API JSON configuree par l'utilisateur.

        On attend un objet contenant un champ prix. On cherche le produit par
        son code d'extension/nom ; format laisse souple car non standardise.
        """
        http = HttpClient(self.settings)
        try:
            query = product.set_code or product.name
            data = http.get_json(api_base.rstrip("/") + "/search", params={"q": query})
            price = _extract_price(data)
            if price is not None:
                return ReferenceResult(price=price, source="zebradex", note="via API configuree")
        finally:
            http.close()
        return ReferenceResult(
            price=product.reference_price, source="manual", note="produit non trouve via API"
        )


def _extract_price(data) -> float | None:
    """Cherche un champ de prix plausible dans une reponse JSON arbitraire."""
    keys = ("price", "prix", "cote", "market_price", "value")
    if isinstance(data, dict):
        for k in keys:
            if k in data:
                try:
                    return float(str(data[k]).replace(",", "."))
                except (ValueError, TypeError):
                    pass
        for v in data.values():
            found = _extract_price(v)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _extract_price(item)
            if found is not None:
                return found
    return None
