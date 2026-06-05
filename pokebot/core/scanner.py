"""Cycle de scan : pour chaque produit x chaque boutique, recupere prix/stock,
calcule l'ecart vs la cote, declenche les alertes et historise tout.

Robuste : l'echec d'une boutique n'interrompt pas le cycle ; chaque echec est
enregistre avec sa raison (pour le rapport des sites en echec).
"""
from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters import build_adapter
from ..adapters.base import ProductResult
from ..config import settings
from ..database import SessionLocal
from ..image_match import confirms, image_similarity
from ..models import Alert, Observation, Product, ProductShop, ScanRun, Shop, utcnow
from ..notifications import build_payload, dispatch
from ..reference import get_provider, refresh_reference
from ..utils.errors import AdapterError
from ..utils.http import HttpClient
from ..utils.logging import get_logger
from .alerts import compute_discount, evaluate, signature

log = get_logger("scanner")

_scan_lock = threading.Lock()


def is_scanning() -> bool:
    return _scan_lock.locked()


def run_scan(trigger: str = "manual") -> int:
    """Lance un cycle complet. Renvoie l'id du ScanRun. Mono-instance (lock)."""
    if not _scan_lock.acquire(blocking=False):
        log.info("Scan deja en cours, demande ignoree.")
        return -1
    try:
        return _run_scan(trigger)
    finally:
        _scan_lock.release()


def _run_scan(trigger: str) -> int:
    db: Session = SessionLocal()
    http = HttpClient(settings)
    scan = ScanRun(started_at=utcnow(), status="running", trigger=trigger, summary={})
    db.add(scan)
    db.commit()  # visible immediatement par l'UI (statut "running")
    scan_id = scan.id
    log.info("Scan #%s demarre (%s)", scan_id, trigger)

    summary = {
        "observations": 0,
        "found": 0,
        "alerts": 0,
        "failures": 0,
        "shop_failures": {},
    }
    try:
        products = list(db.scalars(select(Product).where(Product.enabled.is_(True))))
        shops = list(db.scalars(select(Shop).where(Shop.enabled.is_(True))))
        summary["products"] = len(products)
        summary["shops"] = len(shops)

        # 1) Rafraichir les cotes de reference (au plus 1x/jour selon provider)
        provider = get_provider(settings)
        for product in products:
            try:
                refresh_reference(db, product, provider, settings)
            except Exception as exc:  # une cote en echec ne casse pas le scan
                log.warning("Cote %s indisponible: %s", product.name, exc)
        db.commit()

        # 2) Pour chaque boutique, chaque produit
        for shop in shops:
            adapter = build_adapter(shop, http, settings)
            for product in products:
                link = _get_link(db, product.id, shop.id)
                if link is not None and not link.enabled:
                    continue
                obs = _check_one(db, scan_id, shop, adapter, product, link, http, summary)
                db.add(obs)
                summary["observations"] += 1
            db.commit()  # progression + resultats partiels visibles a chaque boutique

        scan.status = "done"
    except Exception as exc:  # garde-fou global
        log.exception("Scan #%s en erreur: %s", scan_id, exc)
        scan.status = "error"
        summary["error"] = str(exc)
    finally:
        http.close()
        scan.finished_at = utcnow()
        scan.summary = summary
        db.add(scan)
        db.commit()
        log.info(
            "Scan #%s termine: %s observations, %s trouves, %s alertes, %s echecs",
            scan_id, summary["observations"], summary["found"], summary["alerts"], summary["failures"],
        )
        db.close()
    return scan_id


def _check_one(
    db: Session,
    scan_id: int,
    shop: Shop,
    adapter,
    product: Product,
    link: ProductShop | None,
    http: HttpClient,
    summary: dict,
) -> Observation:
    obs = Observation(
        scan_id=scan_id,
        product_id=product.id,
        shop_id=shop.id,
        reference_price=product.reference_price,
        checked_at=utcnow(),
    )
    try:
        if adapter is None:
            raise AdapterError(f"adaptateur '{shop.adapter}' inconnu")
        result: ProductResult = adapter.fetch(product, link)
        _fill_obs(obs, result)
        obs.ok = True

        if result.found:
            summary["found"] += 1
            confident, img_score = _confidence(product, result, http)
            obs.image_match_score = img_score

            decision = evaluate(
                db, product, shop, result.price, result.stock_status,
                product.reference_price, settings, confident,
            )
            obs.discount_pct = decision.discount_pct
            if decision.should_alert:
                _send_alert(db, product, shop, result)
                obs.alerted = True
                summary["alerts"] += 1
                log.info("ALERTE %s @ %s : %.2f (-%.0f%%)",
                         product.name, shop.name, result.price, decision.discount_pct)
    except AdapterError as exc:
        obs.ok = False
        obs.error = f"{type(exc).__name__.replace('Error', '')}: {exc}"
        summary["failures"] += 1
        summary["shop_failures"][shop.name] = str(exc)
    except Exception as exc:
        obs.ok = False
        obs.error = f"Erreur inattendue: {exc}"
        summary["failures"] += 1
        summary["shop_failures"][shop.name] = str(exc)
    return obs


def _fill_obs(obs: Observation, result: ProductResult) -> None:
    obs.found = result.found
    obs.price = result.price
    obs.currency = result.currency
    obs.available = result.available
    obs.stock_status = result.stock_status
    obs.url = result.url
    obs.title = result.title
    obs.match_score = result.match_score
    if obs.reference_price and result.price:
        obs.discount_pct = compute_discount(obs.reference_price, result.price)


def _confidence(product: Product, result: ProductResult, http: HttpClient) -> tuple[bool, float | None]:
    """Confirmation secondaire par image. Renvoie (confiant, score_image)."""
    name_score = result.match_score or 0.0
    base_confident = name_score >= settings.match_min_score
    if not (settings.image_match_enabled and product.image_url and result.image_url):
        return base_confident, None
    try:
        ref_bytes = http.get_bytes(product.image_url)
        cand_bytes = http.get_bytes(result.image_url)
    except Exception:
        return base_confident, None
    distance = image_similarity(ref_bytes, cand_bytes)
    if distance is None:
        return base_confident, None
    verdict = confirms(distance, settings.image_match_max_distance)
    if verdict is True:
        return True, float(distance)  # image confirme : on conforte
    # image en desaccord : on exige un nom tres proche pour rester confiant
    return name_score >= 95.0, float(distance)


def _send_alert(db: Session, product: Product, shop: Shop, result: ProductResult) -> None:
    discount = compute_discount(product.reference_price, result.price)
    payload = build_payload(
        product, shop, result.price, product.reference_price, discount,
        result.stock_status, result.url, result.currency, result.image_url,
    )
    channels = dispatch(payload, settings)
    db.add(
        Alert(
            product_id=product.id,
            shop_id=shop.id,
            signature=signature(product.id, shop.id),
            price=result.price,
            reference_price=product.reference_price,
            discount_pct=discount,
            stock_status=result.stock_status,
            url=result.url,
            channels=channels,
            sent_at=utcnow(),
        )
    )


def _get_link(db: Session, product_id: int, shop_id: int) -> ProductShop | None:
    return db.scalars(
        select(ProductShop)
        .where(ProductShop.product_id == product_id, ProductShop.shop_id == shop_id)
        .limit(1)
    ).first()
