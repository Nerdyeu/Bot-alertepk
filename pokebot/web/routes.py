"""Routes web : pages (dashboard, produits, sites) + API JSON."""
from __future__ import annotations

import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters import list_adapter_types
from ..config import settings
from ..core import scanner
from ..database import SessionLocal
from ..models import Observation, Product, ProductShop, ReferencePoint, ScanRun, Shop, utcnow
from .schemas import LinkIn, ProductIn, ProductReferenceIn, ShopIn
from .serializers import observation_to_dict, product_to_dict, shop_to_dict

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================== Pages ===========================
@router.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/products", response_class=HTMLResponse)
def page_products(request: Request):
    return templates.TemplateResponse(request, "products.html")


@router.get("/shops", response_class=HTMLResponse)
def page_shops(request: Request):
    return templates.TemplateResponse(request, "shops.html")


# =========================== API : scan ===========================
@router.post("/api/scan")
def api_trigger_scan():
    if scanner.is_scanning():
        return {"status": "running", "message": "Un scan est deja en cours."}
    threading.Thread(target=scanner.run_scan, args=("manual",), daemon=True).start()
    return {"status": "started"}


@router.get("/api/summary")
def api_summary(db: Session = Depends(get_db)):
    last = db.scalars(select(ScanRun).order_by(ScanRun.started_at.desc()).limit(1)).first()
    return {
        "scanning": scanner.is_scanning(),
        "last_scan": (
            {
                "id": last.id,
                "status": last.status,
                "trigger": last.trigger,
                "started_at": last.started_at.isoformat() if last.started_at else None,
                "finished_at": last.finished_at.isoformat() if last.finished_at else None,
                "summary": last.summary or {},
            }
            if last
            else None
        ),
        "global_threshold_pct": settings.global_threshold_pct,
        "scan_interval_minutes": settings.scan_interval_minutes,
        "enable_stock_filter": settings.enable_stock_filter,
        "channels": settings.channels,
        "reference_provider": settings.reference_provider,
    }


# =========================== API : resultats ===========================
@router.get("/api/results")
def api_results(db: Session = Depends(get_db)):
    products = {p.id: p for p in db.scalars(select(Product))}
    shops = {s.id: s for s in db.scalars(select(Shop))}
    # Derniere observation par couple (produit, boutique)
    rows = db.scalars(
        select(Observation).order_by(Observation.checked_at.desc()).limit(5000)
    )
    seen: dict[tuple[int, int], Observation] = {}
    for obs in rows:
        key = (obs.product_id, obs.shop_id)
        if key not in seen:
            seen[key] = obs
    results = [
        observation_to_dict(o, products.get(o.product_id), shops.get(o.shop_id), settings)
        for o in seen.values()
    ]
    results.sort(key=lambda r: (r["discount_pct"] is None, -(r["discount_pct"] or 0)))
    return {"results": results}


@router.get("/api/failures")
def api_failures(db: Session = Depends(get_db)):
    last = db.scalars(select(ScanRun).order_by(ScanRun.started_at.desc()).limit(1)).first()
    if not last:
        return {"failures": []}
    products = {p.id: p for p in db.scalars(select(Product))}
    shops = {s.id: s for s in db.scalars(select(Shop))}
    obs = db.scalars(
        select(Observation).where(
            Observation.scan_id == last.id, Observation.ok.is_(False)
        )
    )
    failures = [
        {
            "shop_name": shops[o.shop_id].name if o.shop_id in shops else f"#{o.shop_id}",
            "product_name": products[o.product_id].name if o.product_id in products else f"#{o.product_id}",
            "error": o.error,
        }
        for o in obs
    ]
    return {"scan_id": last.id, "failures": failures}


@router.get("/api/zebradex/search")
def api_zebradex_search(q: str):
    """Recherche de produits scelles sur ZebraDex, pour l'ajout rapide dans l'UI."""
    from ..reference.zebradex import search_sealed

    query = (q or "").strip()
    if len(query) < 2:
        return {"results": []}
    try:
        return {"results": search_sealed(settings, query)}
    except Exception as exc:
        return {"results": [], "error": str(exc)}


@router.get("/api/history")
def api_history(product_id: int, db: Session = Depends(get_db)):
    points = db.scalars(
        select(ReferencePoint)
        .where(ReferencePoint.product_id == product_id)
        .order_by(ReferencePoint.recorded_at.asc())
    )
    return {
        "product_id": product_id,
        "points": [
            {"t": p.recorded_at.isoformat(), "price": p.price, "source": p.source} for p in points
        ],
    }


# =========================== API : produits ===========================
@router.get("/api/products")
def api_products(db: Session = Depends(get_db)):
    products = db.scalars(select(Product).order_by(Product.name))
    return {"products": [product_to_dict(p, settings) for p in products]}


@router.post("/api/products")
def api_create_product(body: ProductIn, db: Session = Depends(get_db)):
    product = Product(**body.model_dump())
    if product.reference_price is not None:
        product.reference_updated_at = utcnow()  # source vient du body (manual ou zebradex)
    db.add(product)
    db.commit()
    db.refresh(product)
    if product.reference_price is not None:
        _record_reference_point(db, product)
    return product_to_dict(product, settings)


@router.put("/api/products/{product_id}")
def api_update_product(product_id: int, body: ProductIn, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "produit introuvable")
    old_ref = product.reference_price
    # On ne touche pas a reference_source via le formulaire d'edition.
    for field, value in body.model_dump(exclude={"reference_source"}).items():
        setattr(product, field, value)
    if product.reference_price is not None and product.reference_price != old_ref:
        product.reference_source = "manual"
        product.reference_updated_at = utcnow()
    db.commit()
    db.refresh(product)
    if product.reference_price is not None and product.reference_price != old_ref:
        _record_reference_point(db, product)
    return product_to_dict(product, settings)


@router.post("/api/products/{product_id}/reference")
def api_set_reference(product_id: int, body: ProductReferenceIn, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "produit introuvable")
    product.reference_price = body.price
    product.reference_source = "manual"
    product.reference_updated_at = utcnow()
    db.commit()
    db.refresh(product)
    _record_reference_point(db, product)
    return product_to_dict(product, settings)


@router.delete("/api/products/{product_id}")
def api_delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "produit introuvable")
    db.delete(product)
    db.commit()
    return {"deleted": product_id}


@router.post("/api/products/{product_id}/links")
def api_set_link(product_id: int, body: LinkIn, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "produit introuvable")
    link = db.scalars(
        select(ProductShop).where(
            ProductShop.product_id == product_id, ProductShop.shop_id == body.shop_id
        )
    ).first()
    if link is None:
        link = ProductShop(product_id=product_id, shop_id=body.shop_id)
        db.add(link)
    link.direct_url = body.direct_url
    link.search_query = body.search_query
    link.enabled = body.enabled
    db.commit()
    db.refresh(product)
    return product_to_dict(product, settings)


@router.delete("/api/products/{product_id}/links/{shop_id}")
def api_delete_link(product_id: int, shop_id: int, db: Session = Depends(get_db)):
    link = db.scalars(
        select(ProductShop).where(
            ProductShop.product_id == product_id, ProductShop.shop_id == shop_id
        )
    ).first()
    if link:
        db.delete(link)
        db.commit()
    return {"deleted": True}


# =========================== API : boutiques ===========================
@router.get("/api/shops")
def api_shops(db: Session = Depends(get_db)):
    shops = db.scalars(select(Shop).order_by(Shop.name))
    return {"shops": [shop_to_dict(s) for s in shops], "adapter_types": list_adapter_types()}


@router.post("/api/shops")
def api_create_shop(body: ShopIn, db: Session = Depends(get_db)):
    if db.scalars(select(Shop).where(Shop.key == body.key)).first():
        raise HTTPException(400, f"cle '{body.key}' deja utilisee")
    shop = Shop(**body.model_dump())
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop_to_dict(shop)


@router.put("/api/shops/{shop_id}")
def api_update_shop(shop_id: int, body: ShopIn, db: Session = Depends(get_db)):
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404, "boutique introuvable")
    for field, value in body.model_dump().items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop_to_dict(shop)


@router.delete("/api/shops/{shop_id}")
def api_delete_shop(shop_id: int, db: Session = Depends(get_db)):
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(404, "boutique introuvable")
    db.delete(shop)
    db.commit()
    return {"deleted": shop_id}


# =========================== helpers ===========================
def _record_reference_point(db: Session, product: Product) -> None:
    if product.reference_price is None:
        return
    db.add(
        ReferencePoint(
            product_id=product.id,
            price=product.reference_price,
            source=product.reference_source or "manual",
            recorded_at=utcnow(),
        )
    )
    db.commit()
