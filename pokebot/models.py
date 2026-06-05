"""Modeles de donnees : boutiques, produits, observations de prix, alertes."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> dt.datetime:
    # UTC "naif" : coherent avec le stockage SQLite (DateTime sans fuseau),
    # evite les comparaisons aware/naive lors de l'anti-spam.
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Shop(Base):
    """Une boutique surveillee. `adapter` choisit le module d'extraction."""

    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    base_url: Mapped[str] = mapped_column(String(255))
    adapter: Mapped[str] = mapped_column(String(40), default="shopify")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Product(Base):
    """Un produit precis a surveiller, avec sa cote de reference."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    set_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    reference_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_source: Mapped[str] = mapped_column(String(40), default="manual")
    reference_updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    threshold_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # None => seuil global
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    links: Mapped[list["ProductShop"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductShop(Base):
    """Mapping optionnel produit<->boutique : URL directe ou requete dediee."""

    __tablename__ = "product_shops"
    __table_args__ = (UniqueConstraint("product_id", "shop_id", name="uq_product_shop"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    direct_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    search_query: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["Product"] = relationship(back_populates="links")


class Observation(Base):
    """Resultat d'une verification (prix/stock) pour un produit sur une boutique."""

    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scan_runs.id"), nullable=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))

    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    found: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stock_status: Mapped[str] = mapped_column(String(20), default="unknown")
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    reference_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False)

    checked_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ReferencePoint(Base):
    """Historique de la cote de reference (ZebraDex) pour le graphique."""

    __tablename__ = "reference_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    price: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Alert(Base):
    """Alerte envoyee (sert aussi a l'anti-spam via la signature produit/boutique)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    signature: Mapped[str] = mapped_column(String(80), index=True)

    price: Mapped[float] = mapped_column(Float)
    reference_price: Mapped[float] = mapped_column(Float)
    discount_pct: Mapped[float] = mapped_column(Float)
    stock_status: Mapped[str] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    channels: Mapped[dict] = mapped_column(JSON, default=dict)
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ScanRun(Base):
    """Un cycle de verification (auto ou manuel)."""

    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|done|error
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # auto|manual
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
