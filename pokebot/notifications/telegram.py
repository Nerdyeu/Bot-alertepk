"""Notification Telegram via bot (token + chat_id)."""
from __future__ import annotations

import html

import httpx

from .base import Notifier


class TelegramNotifier(Notifier):
    name = "telegram"

    def configured(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    def send(self, payload: dict) -> None:
        name = html.escape(payload["product_name"])
        shop = html.escape(payload["shop_name"])
        text = (
            f"💸 <b>{name}</b>  (-{payload['discount_pct']:.0f}%)\n"
            f"🏪 {shop}\n"
            f"💶 <b>{payload['price']:.2f} {payload['currency']}</b> "
            f"(cote ZebraDex {payload['reference_price']:.2f})\n"
            f"📦 Stock : {html.escape(payload['stock_status'])}\n"
        )
        if payload.get("url"):
            text += f'\n<a href="{html.escape(payload["url"])}">➡️ Voir / acheter</a>'
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        resp = httpx.post(
            url,
            json={
                "chat_id": self.settings.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
