from pokebot.core import stock


def test_waiting_room_is_uncertain():
    assert stock.classify("Vous êtes dans la file d'attente") == stock.UNCERTAIN
    assert stock.classify("Disponible sur invitation uniquement") == stock.UNCERTAIN
    assert stock.classify("Précommande — sortie le 12/09") == stock.UNCERTAIN


def test_out_of_stock():
    assert stock.classify("Rupture de stock") == stock.OUT_OF_STOCK
    assert stock.classify("Produit épuisé") == stock.OUT_OF_STOCK


def test_in_stock():
    assert stock.classify("En stock — Ajouter au panier") == stock.IN_STOCK


def test_unknown():
    assert stock.classify("") == stock.UNKNOWN
    assert stock.classify("texte neutre sans info") == stock.UNKNOWN
