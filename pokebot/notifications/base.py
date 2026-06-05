"""Contrat des notifieurs."""
from __future__ import annotations

from ..config import Settings


class Notifier:
    name = "base"

    def __init__(self, settings: Settings):
        self.settings = settings

    def configured(self) -> bool:  # pragma: no cover
        raise NotImplementedError

    def send(self, payload: dict) -> None:  # pragma: no cover
        raise NotImplementedError
