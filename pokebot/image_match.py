"""Verification secondaire par image (perceptual hash).

Optionnelle : si Pillow/ImageHash ne sont pas installes, ou si aucune image
n'est disponible, on renvoie simplement None sans casser le scan.
"""
from __future__ import annotations

import io

from .utils.logging import get_logger

log = get_logger("image")

try:  # dependances optionnelles
    import imagehash
    from PIL import Image

    _AVAILABLE = True
except Exception:  # pragma: no cover
    _AVAILABLE = False


def _phash(data: bytes):
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return imagehash.phash(img)


def image_similarity(ref_bytes: bytes | None, cand_bytes: bytes | None) -> int | None:
    """Distance de Hamming entre les phash (0 = identique). None si indisponible."""
    if not _AVAILABLE or not ref_bytes or not cand_bytes:
        return None
    try:
        return _phash(ref_bytes) - _phash(cand_bytes)
    except Exception as exc:  # image illisible, format exotique...
        log.debug("comparaison image impossible: %s", exc)
        return None


def confirms(distance: int | None, max_distance: int) -> bool | None:
    """True/False si une distance a pu etre calculee, sinon None (non concluant)."""
    if distance is None:
        return None
    return distance <= max_distance
