import pytest

import pokebot.adapters.ebay as ebay
from pokebot.config import Settings
from pokebot.models import Product, Shop
from pokebot.utils.errors import BlockedError, NotFoundError


class FakeHttp:
    def __init__(self, payload):
        self.payload = payload
        self.last_params = None

    def get_json(self, url, params=None, headers=None, ignore_robots=False):
        self.last_params = params
        return self.payload


def make_adapter(payload, **settings_kw):
    settings = Settings(ebay_client_id="id", ebay_client_secret="secret",
                        match_min_score=80, **settings_kw)
    shop = Shop(key="ebay", name="eBay", base_url="https://api.ebay.com", adapter="ebay", config={})
    return ebay.EbayAdapter(shop, FakeHttp(payload), settings)


def test_missing_credentials_raises_blocked():
    settings = Settings()  # pas de cles
    shop = Shop(key="ebay", name="eBay", base_url="https://api.ebay.com", adapter="ebay", config={})
    adapter = ebay.EbayAdapter(shop, FakeHttp({}), settings)
    with pytest.raises(BlockedError):
        adapter.fetch(Product(name="ETB Évolutions Prismatiques"), None)


def test_picks_cheapest_matching_listing(monkeypatch):
    monkeypatch.setattr(ebay, "_get_token", lambda *a, **k: "tok")
    payload = {"itemSummaries": [
        {"title": "Pochette plastique protege carte", "price": {"value": "2.00", "currency": "EUR"},
         "itemWebUrl": "https://ebay.fr/itm/1"},
        {"title": "Coffret Dresseur d'Élite Évolutions Prismatiques", "price": {"value": "89.90", "currency": "EUR"},
         "itemWebUrl": "https://ebay.fr/itm/2", "condition": "Neuf",
         "image": {"imageUrl": "https://i.ebayimg.com/2.jpg"}},
        {"title": "ETB Évolutions Prismatiques scellé", "price": {"value": "99.00", "currency": "EUR"},
         "itemWebUrl": "https://ebay.fr/itm/3", "condition": "Neuf"},
    ]}
    adapter = make_adapter(payload)
    res = adapter.fetch(Product(name="ETB Évolutions Prismatiques"), None)
    assert res.found is True
    assert res.price == 89.90  # la moins chere qui correspond (la pochette est ignoree)
    assert res.url.endswith("/itm/2")
    assert "Neuf" in res.title


def test_no_match_raises_not_found(monkeypatch):
    monkeypatch.setattr(ebay, "_get_token", lambda *a, **k: "tok")
    payload = {"itemSummaries": [
        {"title": "Sleeves Dragon Shield", "price": {"value": "9.00", "currency": "EUR"}},
    ]}
    adapter = make_adapter(payload)
    with pytest.raises(NotFoundError):
        adapter.fetch(Product(name="ETB Évolutions Prismatiques"), None)
