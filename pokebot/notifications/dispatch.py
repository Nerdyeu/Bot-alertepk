"""Construction du message d'alerte et envoi vers les canaux configures."""
from __future__ import annotations

from ..config import Settings
from ..models import Product, Shop
from ..utils.logging import get_logger
from .discord import DiscordNotifier
from .telegram import TelegramNotifier

log = get_logger("notify")

_NOTIFIERS = {
    "discord": DiscordNotifier,
    "telegram": TelegramNotifier,
}


def build_payload(
    product: Product, shop: Shop, price: float, reference_price: float,
    discount_pct: float, stock_status: str, url: str | None, currency: str = "EUR",
    image_url: str | None = None,
) -> dict:
    return {
        "product_name": product.name,
        "set_code": product.set_code,
        "shop_name": shop.name,
        "price": price,
        "currency": currency,
        "reference_price": reference_price,
        "discount_pct": discount_pct,
        "stock_status": stock_status,
        "url": url,
        "image_url": image_url or product.image_url,
    }


def dispatch(payload: dict, settings: Settings) -> dict:
    """Envoie l'alerte vers chaque canal active. Renvoie le statut par canal."""
    results: dict[str, str] = {}
    for channel in settings.channels:
        cls = _NOTIFIERS.get(channel)
        if cls is None:
            results[channel] = "canal inconnu"
            continue
        notifier = cls(settings)
        if not notifier.configured():
            results[channel] = "non configure (.env)"
            continue
        try:
            notifier.send(payload)
            results[channel] = "ok"
        except Exception as exc:
            results[channel] = f"erreur: {exc}"
            log.warning("Notification %s en echec: %s", channel, exc)
    return results
