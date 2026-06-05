"""Notification Discord via webhook (le plus simple a mettre en place)."""
from __future__ import annotations

import httpx

from .base import Notifier


class DiscordNotifier(Notifier):
    name = "discord"

    def configured(self) -> bool:
        return bool(self.settings.discord_webhook_url)

    def send(self, payload: dict) -> None:
        embed = {
            "title": f"💸 {payload['product_name']} — -{payload['discount_pct']:.0f}%",
            "url": payload.get("url"),
            "color": 0x2ECC71,
            "fields": [
                {"name": "Boutique", "value": payload["shop_name"], "inline": True},
                {
                    "name": "Prix",
                    "value": f"{payload['price']:.2f} {payload['currency']}",
                    "inline": True,
                },
                {
                    "name": "Cote ZebraDex",
                    "value": f"{payload['reference_price']:.2f} {payload['currency']}",
                    "inline": True,
                },
                {"name": "Stock", "value": payload["stock_status"], "inline": True},
            ],
            "description": f"[➡️ Voir / acheter]({payload['url']})" if payload.get("url") else "",
        }
        if payload.get("image_url"):
            embed["thumbnail"] = {"url": payload["image_url"]}
        body = {"username": "PokeAlertBot", "embeds": [embed]}
        resp = httpx.post(self.settings.discord_webhook_url, json=body, timeout=15.0)
        resp.raise_for_status()
