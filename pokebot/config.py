"""Configuration centralisee, chargee depuis l'environnement / fichier .env.

Aucun secret n'est ecrit en dur : tout vient de variables d'environnement
(voir .env.example).
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Serveur web
    host: str = "127.0.0.1"
    port: int = 8000

    # Base de donnees
    database_url: str = f"sqlite:///{DATA_DIR / 'pokebot.db'}"

    # Planification / reseau
    scan_interval_minutes: int = 60
    request_timeout: float = 20.0
    rate_limit_seconds: float = 2.0
    respect_robots: bool = True
    user_agent: str = (
        "PokeAlertBot/1.0 (+https://github.com/nerdyeu/bot-alertepk; "
        "veille tarifaire personnelle)"
    )

    # Logique d'alerte
    global_threshold_pct: float = 5.0
    enable_stock_filter: bool = True
    alert_min_price_drop_pct: float = 2.0
    alert_cooldown_hours: float = 24.0
    match_min_score: float = 80.0
    image_match_enabled: bool = True
    image_match_max_distance: int = 12

    # Prix de reference (ZebraDex)
    reference_provider: str = "manual"  # manual | zebradex
    reference_refresh_hours: float = 24.0
    zebradex_api_base: str | None = None
    zebradex_email: str | None = None
    zebradex_password: str | None = None

    # Notifications
    notify_channels: str = ""
    discord_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @property
    def channels(self) -> list[str]:
        return [c.strip().lower() for c in self.notify_channels.split(",") if c.strip()]


settings = Settings()
