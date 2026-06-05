"""Correspondance de nom tolerante (orthographe / format / synonymes FR-EN)."""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

# Code d'extension/serie type "ME04", "SV08", "EV6.5"... discriminant fort.
_SETCODE_RE = re.compile(r"\b([a-z]{2,3}\d{1,3}(?:[.\-]\d{1,2})?)\b")

# Synonymes normalises -> on les reduit a une forme canonique courte.
_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\belite trainer box\b", "etb"),
    (r"\bcoffret dresseur d? ?elite\b", "etb"),
    (r"\bdresseur d elite\b", "etb"),
    (r"\bbooster box\b", "display"),
    (r"\bbooster bundle\b", "bundle"),
    (r"\bcoffret\b", "coffret"),
    (r"\bpokemon\b", ""),
    (r"\bjcc\b", ""),
    (r"\btcg\b", ""),
    (r"\bcartes?\b", ""),
    (r"\bscelle?\b", ""),
    (r"\bneuf\b", ""),
    (r"\bversion (francaise|fr)\b", ""),
    (r"\bfrancais(e)?\b", ""),
    (r"\bedition\b", ""),
]


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def normalize(text: str) -> str:
    """Minuscule, sans accent ni ponctuation, synonymes reduits, espaces compactes."""
    if not text:
        return ""
    text = strip_accents(text).lower()
    text = text.replace("’", " ").replace("'", " ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    for pattern, repl in _REPLACEMENTS:
        text = re.sub(pattern, repl, text)
    return re.sub(r"\s+", " ", text).strip()


def set_codes(text: str) -> set[str]:
    return set(_SETCODE_RE.findall(normalize(text)))


def score(query: str, candidate: str) -> float:
    """Score 0-100 de ressemblance, avec bonus/malus sur le code d'extension."""
    nq, nc = normalize(query), normalize(candidate)
    if not nq or not nc:
        return 0.0
    base = float(fuzz.token_set_ratio(nq, nc))

    q_codes, c_codes = set_codes(query), set_codes(candidate)
    if q_codes:
        if q_codes & c_codes:
            base = min(100.0, base + 8.0)  # meme code d'extension : on conforte
        elif c_codes:
            base = max(0.0, base - 25.0)  # code d'extension different : forte penalite
    return round(base, 1)


def best_match(
    query: str, candidates: list[tuple[str, dict]], min_score: float
) -> tuple[dict | None, float]:
    """Renvoie (payload du meilleur candidat, score) si >= min_score, sinon (None, score)."""
    best_payload: dict | None = None
    best_score = 0.0
    for title, payload in candidates:
        s = score(query, title)
        if s > best_score:
            best_score, best_payload = s, payload
    if best_score >= min_score:
        return best_payload, best_score
    return None, best_score
