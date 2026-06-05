import pokebot.reference.zebradex as zbd
from pokebot.config import Settings
from pokebot.models import Product

SAMPLE = [
    {"name": "Coffret Dresseur d'Élite de Étincelles Déferlantes", "code": "ETB",
     "url": "https://zebradex.fr/.../3073", "image_url": "https://media/3073.webp", "price": 118.11},
    {"name": "Coffret Dresseur d'Élite Serpente-Eau de Forces Temporelles", "code": "ETB",
     "url": "https://zebradex.fr/.../3108", "image_url": "https://media/3108.webp", "price": 154.5},
]


class FakeHttp:
    def __init__(self, settings, payload):
        self.payload = payload

    def get_json(self, url, params=None, headers=None, ignore_robots=False):
        return self.payload

    def close(self):
        pass


def make_provider(monkeypatch, payload):
    monkeypatch.setattr(zbd, "HttpClient", lambda settings: FakeHttp(settings, payload))
    return zbd.ZebradexReferenceProvider(Settings(match_min_score=80))


def test_build_query_strips_generic_and_setcode():
    assert zbd._build_query("ETB Chaos Ascendant ME04") == "chaos ascendant"
    assert zbd._build_query("Coffret Dresseur d'Élite Étincelles Déferlantes") == "etincelles deferlantes"
    # si tout est generique, on garde au moins les mots restants
    assert zbd._build_query("Coffret Dresseur") != ""


def test_zebradex_picks_best_match(monkeypatch):
    provider = make_provider(monkeypatch, SAMPLE)
    product = Product(name="Coffret Dresseur d'Élite Étincelles Déferlantes")
    res = provider.get(product)
    assert res.source == "zebradex"
    assert res.price == 118.11
    assert res.image_url == "https://media/3073.webp"
    assert res.ref_url.endswith("3073")


def test_zebradex_fallback_to_manual(monkeypatch):
    provider = make_provider(monkeypatch, [])
    product = Product(name="Produit inexistant XYZ", reference_price=42.0)
    res = provider.get(product)
    assert res.price == 42.0
    assert res.source == "manual"


def test_zebradex_network_error_falls_back(monkeypatch):
    class Boom:
        def __init__(self, settings):
            pass

        def get_json(self, *a, **k):
            raise RuntimeError("page de verification anti-bot")

        def close(self):
            pass

    monkeypatch.setattr(zbd, "HttpClient", Boom)
    provider = zbd.ZebradexReferenceProvider(Settings())
    product = Product(name="Truc", reference_price=10.0)
    res = provider.get(product)
    assert res.price == 10.0
