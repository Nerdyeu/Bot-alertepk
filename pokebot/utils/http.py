"""Client HTTP poli : User-Agent honnete, rate-limiting par domaine,
respect de robots.txt, et detection des pages de protection anti-bot.
"""
from __future__ import annotations

import threading
import time
import urllib.robotparser as robotparser
from urllib.parse import urlparse

import httpx

from ..config import Settings
from .errors import BlockedError, ChallengeError, StructureError
from .logging import get_logger

log = get_logger("http")

# Signatures de pages de "challenge" (verification / protection anti-bot).
_CHALLENGE_MARKERS = (
    "verifying your connection",
    "checking your browser",
    "verification de votre",
    "just a moment",
    "attention required",
    "cf-browser-verification",
    "px-captcha",
    "captcha-delivery",
    "enable javascript and cookies to continue",
)


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


class HttpClient:
    """Enveloppe httpx.Client, partagee pour un cycle de scan."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = httpx.Client(
            timeout=settings.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
            },
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._lock = threading.Lock()

    # -- politesse ----------------------------------------------------------
    def _throttle(self, url: str) -> None:
        dom = domain_of(url)
        with self._lock:
            last = self._last_request.get(dom, 0.0)
            wait = self.settings.rate_limit_seconds - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
            self._last_request[dom] = time.monotonic()

    def _robots_for(self, url: str) -> robotparser.RobotFileParser | None:
        dom = domain_of(url)
        if dom in self._robots:
            return self._robots[dom]
        parsed = urlparse(url)
        rp = robotparser.RobotFileParser()
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            resp = self._client.get(robots_url, timeout=10.0)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp = None  # pas de robots.txt accessible -> on n'interdit rien
        except Exception:
            rp = None
        self._robots[dom] = rp
        return rp

    def _check_allowed(self, url: str) -> None:
        if not self.settings.respect_robots:
            return
        rp = self._robots_for(url)
        if rp is not None and not rp.can_fetch(self.settings.user_agent, url):
            raise BlockedError(f"robots.txt interdit l'acces a {url}")

    # -- requetes -----------------------------------------------------------
    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        self._check_allowed(url)
        self._throttle(url)
        try:
            resp = self._client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise BlockedError(f"timeout ({self.settings.request_timeout}s)") from exc
        except httpx.HTTPError as exc:
            raise BlockedError(f"erreur reseau: {exc}") from exc

        if resp.status_code in (401, 403):
            raise BlockedError(f"acces refuse (HTTP {resp.status_code})")
        if resp.status_code == 429:
            raise BlockedError("trop de requetes (HTTP 429) — rate-limit du site")
        self._detect_challenge(resp)
        return resp

    def _detect_challenge(self, resp: httpx.Response) -> None:
        ctype = resp.headers.get("content-type", "")
        if "text/html" not in ctype:
            return
        snippet = resp.text[:4000].lower()
        if any(m in snippet for m in _CHALLENGE_MARKERS):
            raise ChallengeError(
                "page de verification anti-bot detectee "
                "(souvent liee a l'IP : reessayez depuis votre PC perso)"
            )

    def get_json(self, url: str, params: dict | None = None) -> dict:
        resp = self.get(url, params=params)
        if resp.status_code == 404:
            raise StructureError(f"endpoint introuvable (HTTP 404) : {url}")
        ctype = resp.headers.get("content-type", "")
        if "json" not in ctype and not resp.text.lstrip().startswith(("{", "[")):
            # Reponse HTML la ou on attend du JSON : challenge probable.
            self._detect_challenge(resp)
            raise StructureError("reponse non-JSON (structure changee ou protection)")
        try:
            return resp.json()
        except ValueError as exc:
            raise StructureError(f"JSON invalide: {exc}") from exc

    def get_bytes(self, url: str) -> bytes:
        resp = self.get(url)
        return resp.content

    def close(self) -> None:
        self._client.close()
