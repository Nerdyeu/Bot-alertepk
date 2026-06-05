import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pokebot.config import Settings
from pokebot.core.alerts import compute_discount, evaluate, signature, threshold_for
from pokebot.core.stock import IN_STOCK, OUT_OF_STOCK
from pokebot.database import Base
from pokebot.models import Alert, Product, Shop, utcnow


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def base_settings(**kw):
    defaults = dict(
        global_threshold_pct=5.0,
        enable_stock_filter=True,
        alert_min_price_drop_pct=2.0,
        alert_cooldown_hours=24.0,
    )
    defaults.update(kw)
    return Settings(**defaults)


def test_compute_discount_and_threshold():
    assert round(compute_discount(100, 90), 1) == 10.0
    p = Product(name="x", threshold_pct=None)
    assert threshold_for(p, base_settings()) == 5.0
    p.threshold_pct = 12
    assert threshold_for(p, base_settings()) == 12


def test_below_threshold_no_alert():
    db = make_session()
    p = Product(name="ETB", reference_price=100.0)
    s = Shop(key="k", name="Shop", base_url="https://x")
    db.add_all([p, s])
    db.commit()
    d = evaluate(db, p, s, price=98.0, stock_status=IN_STOCK, reference_price=100.0, settings=base_settings())
    assert d.should_alert is False  # -2% < 5%


def test_stock_filter_blocks_out_of_stock():
    db = make_session()
    p = Product(name="ETB", reference_price=100.0)
    s = Shop(key="k", name="Shop", base_url="https://x")
    db.add_all([p, s])
    db.commit()
    d = evaluate(db, p, s, price=80.0, stock_status=OUT_OF_STOCK, reference_price=100.0, settings=base_settings())
    assert d.should_alert is False


def test_alert_triggers_and_antispam():
    db = make_session()
    p = Product(name="ETB", reference_price=100.0)
    s = Shop(key="k", name="Shop", base_url="https://x")
    db.add_all([p, s])
    db.commit()
    st = base_settings()

    d = evaluate(db, p, s, price=80.0, stock_status=IN_STOCK, reference_price=100.0, settings=st)
    assert d.should_alert is True
    assert round(d.discount_pct, 0) == 20

    # On enregistre l'alerte -> meme prix ne doit pas re-alerter (anti-spam)
    db.add(Alert(product_id=p.id, shop_id=s.id, signature=signature(p.id, s.id),
                 price=80.0, reference_price=100.0, discount_pct=20.0,
                 stock_status=IN_STOCK, sent_at=utcnow()))
    db.commit()
    d2 = evaluate(db, p, s, price=80.0, stock_status=IN_STOCK, reference_price=100.0, settings=st)
    assert d2.should_alert is False

    # Mais une nouvelle baisse significative re-alerte
    d3 = evaluate(db, p, s, price=70.0, stock_status=IN_STOCK, reference_price=100.0, settings=st)
    assert d3.should_alert is True


def test_confidence_blocks_alert():
    db = make_session()
    p = Product(name="ETB", reference_price=100.0)
    s = Shop(key="k", name="Shop", base_url="https://x")
    db.add_all([p, s])
    db.commit()
    d = evaluate(db, p, s, price=70.0, stock_status=IN_STOCK, reference_price=100.0,
                 settings=base_settings(), confident=False)
    assert d.should_alert is False
