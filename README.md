# ⚡ Bot-alertepk

Bot de **surveillance de prix** pour produits Pokémon scellés (ETB, bundles, displays,
coffrets…) vendus en France.

Il compare le prix de chaque produit sur une liste de boutiques à la **cote de référence
ZebraDex**, et **alerte avec un lien direct** dès qu'une boutique passe sous un seuil de
réduction que vous choisissez. **Aucun achat automatique** : alerte + redirection seulement.

> ⚠️ Le bot ne saisit jamais d'identifiants / carte bancaire et ne contourne aucun CAPTCHA,
> file d'attente ou page d'authentification. Les sites qui bloquent sont **signalés en échec**,
> proprement.

---

## ✨ Fonctionnalités

- **Produits surveillés** : ajout / modification / suppression depuis l'interface, avec seuil
  global **ou par produit**, image optionnelle, et **URL directe optionnelle** par boutique.
- **Adaptateurs par boutique** (un module = une boutique) :
  - `shopify` → utilise les **endpoints JSON** Shopify (`/products.json`, `/search/suggest.json`,
    `/products/<handle>.json`) plutôt que de parser le HTML.
  - `html` → adaptateur générique piloté par **sélecteurs CSS** (config JSON) pour les sites non Shopify.
  - `blocked` → sites volontairement non scrappés (anti-bot / API officielle requise) → **signalés en échec**.
- **Correspondance produit** : matching de nom **tolérant** (accents, FR/EN, synonymes ETB/Coffret,
  code d'extension type `ME04`) + **confirmation secondaire par image** (perceptual hash) si une image est dispo.
- **Cote de référence ZebraDex** : saisie manuelle (par défaut) ou fournisseur branchable (voir plus bas),
  **mise en cache** (1×/jour max) et **historisée** pour le graphique.
- **Logique d'alerte** : `% = (cote − prix) / cote × 100`, alerte si `% ≥ seuil`, **uniquement en stock**
  (option), avec **détection des files d'attente / waiting rooms** (statut « stock incertain »).
- **Anti-spam** : pas de ré-alerte tant que le prix/stock n'a pas changé significativement (ou cooldown).
- **Notifications** : **Discord (webhook)** et/ou **Telegram**, + affichage dans l'interface.
- **Interface web locale** : tableau de bord filtrable (par site, produit, % de réduction, stock),
  **graphique d'historique de la cote**, **rapport des sites en échec**, **bouton de scan manuel**.
- **Planification** : scan automatique toutes les heures (configurable) + déclenchement manuel.

---

## 🚀 Installation rapide

### Option A — Python (recommandée pour un PC perso)

Prérequis : **Python 3.11+**.

```bash
git clone https://github.com/nerdyeu/bot-alertepk.git
cd bot-alertepk

make install        # crée .venv, installe les dépendances, copie .env.example -> .env
make run            # démarre l'interface + le planificateur
```

Puis ouvrez **http://127.0.0.1:8000**.

> Sans `make` (Windows par ex.) :
> ```bash
> python -m venv .venv
> .venv\Scripts\activate          # (Linux/Mac : source .venv/bin/activate)
> pip install -r requirements.txt
> copy .env.example .env           # (Linux/Mac : cp .env.example .env)
> python -m pokebot serve
> ```

### Option B — Docker (une commande)

```bash
cp .env.example .env     # éditez si besoin (webhooks…)
docker compose up --build -d
```

Interface sur **http://127.0.0.1:8000**. La base SQLite est persistée dans `./data`.

---

## ⚙️ Configuration (`.env`)

Tous les réglages sont dans `.env` (voir `.env.example`). **Aucun secret n'est committé.**

| Variable | Rôle | Défaut |
|---|---|---|
| `GLOBAL_THRESHOLD_PCT` | Seuil d'alerte global (%) | `5` |
| `ENABLE_STOCK_FILTER` | N'alerter que si réellement en stock | `true` |
| `SCAN_INTERVAL_MINUTES` | Fréquence du scan auto | `60` |
| `RATE_LIMIT_SECONDS` | Délai mini entre 2 requêtes vers un même domaine | `2.0` |
| `RESPECT_ROBOTS` | Respecter `robots.txt` | `true` |
| `MATCH_MIN_SCORE` | Score minimal (0–100) pour accepter un produit | `80` |
| `IMAGE_MATCH_ENABLED` | Confirmation par image si dispo | `true` |
| `REFERENCE_PROVIDER` | `manual` ou `zebradex` | `manual` |
| `NOTIFY_CHANNELS` | `discord,telegram` (csv) | _(vide)_ |
| `DISCORD_WEBHOOK_URL` | Webhook Discord | — |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Bot Telegram | — |

### Notifications

- **Discord** : créez un webhook (Paramètres du salon → Intégrations → Webhooks), collez son URL
  dans `DISCORD_WEBHOOK_URL`, et mettez `NOTIFY_CHANNELS=discord`.
- **Telegram** : créez un bot via **@BotFather** (`TELEGRAM_BOT_TOKEN`), récupérez votre `chat_id`
  (par ex. via **@userinfobot**), puis `NOTIFY_CHANNELS=telegram` (ou `discord,telegram`).

Les alertes s'affichent **toujours** dans l'interface, même sans canal configuré.

---

## 🔭 ZebraDex — prix de référence

La **cote de référence** d'un produit est sa valeur sur ZebraDex (`zebradex.fr`). Deux modes
(`REFERENCE_PROVIDER`), **sans jamais contourner d'authentification ni de captcha** :

### `zebradex` (par défaut) — récupération automatique

ZebraDex sert à ses **visiteurs non connectés** un endpoint JSON de recherche qui renvoie la cote des
produits scellés :

```
GET https://zebradex.fr/include/search/autocomplete.php?q=<nom>&lang=fr&type=sealed
→ [{ "name", "code", "url", "image_url", "price", "ebay_url", "cardmarket_url" }, ...]
```

Le bot interroge cet endpoint en **lecture seule**, fait correspondre votre produit par son **nom**
(matching tolérant), récupère `price` comme cote, et en profite pour **auto-remplir l'image** du produit
(utile à la confirmation par image). La cote est **mise en cache** et n'est interrogée qu'**1×/jour max**
(`REFERENCE_REFRESH_HOURS`), avec rate-limiting.

> ⚠️ **robots.txt** : cet endpoint est sous `/include/`, que le `robots.txt` de ZebraDex interdit aux
> crawlers. Le réglage **`ZEBRADEX_IGNORE_ROBOTS=true`** (activé par défaut, votre choix) autorise cette
> requête **uniquement pour ZebraDex**, en lecture seule et 1×/jour. **Le scraping des boutiques, lui,
> respecte toujours robots.txt.** Passez ce réglage à `false` pour basculer en saisie manuelle.

Si un produit n'est pas trouvé sur ZebraDex (ou en cas d'erreur réseau), on **retombe proprement** sur
la cote saisie manuellement.

### `manual` — saisie dans l'interface

`REFERENCE_PROVIDER=manual` : vous saisissez/mettez à jour la cote vous‑même (bouton « cote » sur la page
Produits). Aucune requête vers ZebraDex. La cote est historisée pour le graphique.

> Option avancée : `ZEBRADEX_API_BASE` permet de pointer vers une autre base d'API JSON ; une lecture
> authentifiée avec **vos** identifiants (`ZEBRADEX_EMAIL`/`PASSWORD`) reste possible à brancher dans le
> respect des CGU, mais n'est pas activée par défaut.

L'historique du graphique utilise **uniquement la cote ZebraDex** (source jugée fiable).

---

## 🛒 Boutiques de départ — faisabilité

| Boutique | Adaptateur | Statut | Stratégie |
|---|---|---|---|
| PokeStation, Monpokestore, Hikaru, Fuji Store, Blazing Tail, Arakemon | `shopify` | ✅ activées | endpoints JSON Shopify |
| Magic Bazar, Cartamania, Ludifolie, Otaku Manga | `html` | ⚙️ à configurer | sélecteurs CSS dans la config du site |
| Fnac, Cultura, Amazon, Micromania | `blocked` | ⛔ non scrappées | anti-bot / API officielle requise |
| Cardmarket | `blocked` | ⛔ | **API Cardmarket** officielle (OAuth) requise |
| Vinted, Leboncoin | `blocked` | ⛔ | anti-bot + CGU ; utiliser leurs **alertes natives** |
| **eBay** | `ebay` | ✅ via API | **API officielle Browse** (clé gratuite à configurer) |

> **Note importante (anti-bot & IP).** Plusieurs boutiques Shopify renvoient une page
> *« Verifying your connection… »* aux requêtes venant d'**IP datacenter/cloud**. Depuis votre
> **connexion résidentielle** (votre PC), `products.json` répond normalement. Si une boutique
> apparaît en échec avec « page de vérification anti-bot », c'est souvent lié à l'IP : réessayez
> depuis votre PC, ou augmentez `RATE_LIMIT_SECONDS`.

### Marché secondaire (propre)

- **eBay** : adaptateur **`ebay`** inclus, basé sur l'**API officielle Browse** (aucun scraping).
  1. Crée un compte développeur gratuit sur **https://developer.ebay.com/** → *My Account / Application Keys*.
  2. Récupère ton **App ID (Client ID)** et **Cert ID (Client Secret)** de production.
  3. Mets-les dans `.env` (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`), puis **active** la boutique « eBay »
     dans l'onglet *Sites*.
  - Le bot fait un flux OAuth2 *client credentials*, cherche les annonces (achat immédiat par défaut),
    et renvoie la **moins chère qui correspond** (prix hors frais de port). Filtre configurable dans la
    config de la boutique (ex. neuf seulement : `"filter": "buyingOptions:{FIXED_PRICE},conditionIds:{1000}"`).
- **Cardmarket** : laissé en `blocked` ; nécessite le programme **MKM API** (OAuth). Un adaptateur
  `cardmarket` peut être ajouté sur le même modèle qu'eBay.
- **Vinted / Leboncoin** : **non supportés** volontairement. Protections anti‑bot agressives + CGU
  interdisant le scraping → laissés en `blocked` (signalés comme tels). Pour Vinted, le plus simple et
  100 % légal est d'utiliser ses **alertes natives** (recherche sauvegardée dans l'appli).

---

## 🧩 Ajouter une boutique

1. **Boutique Shopify** : page **Sites** → *Nouveau site* → adaptateur `shopify`, URL de base
   (ex. `https://maboutique.fr`). C'est tout.
2. **Site non Shopify** : adaptateur `html` + une config JSON, par ex. :
   ```json
   {
     "search_url": "https://maboutique.fr/recherche?controller=search&s={query}",
     "result_link_selector": "a.product-thumbnail",
     "price_selector": "span.price",
     "availability_selector": ".product-availability",
     "image_selector": "img.product-cover"
   }
   ```
3. **Nouvel adaptateur en code** : créez `pokebot/adapters/ma_boutique.py` implémentant
   `fetch(product, link) -> ProductResult`, puis enregistrez-le dans `pokebot/adapters/registry.py`.

Pour fiabiliser un produit donné, collez son **URL directe** sur la boutique (page Produits →
*URL/requête par boutique*) : elle est utilisée en priorité au lieu de la recherche par nom.

---

## 🖥️ Utilisation

- **Tableau de bord** (`/`) : résultats du dernier scan, filtres (site / produit / % / stock),
  graphique d'historique de la cote, rapport des sites en échec, bouton **Scanner maintenant**.
- **Produits** (`/products`) : CRUD, seuil par produit, cote manuelle, URL/requête par boutique.
- **Sites** (`/shops`) : CRUD, activation/désactivation, config des adaptateurs.

Lancer un scan unique en ligne de commande :

```bash
python -m pokebot scan
```

---

## 🧪 Tests

```bash
make dev      # installe pytest
make test     # ou: pytest -q
```

---

## 🏗️ Architecture

```
pokebot/
├── config.py            # réglages via .env (pydantic-settings)
├── database.py          # SQLite + SQLAlchemy 2.0
├── models.py            # Shop, Product, ProductShop, Observation, ReferencePoint, Alert, ScanRun
├── matching.py          # correspondance de nom tolérante (+ code d'extension)
├── image_match.py       # confirmation par image (phash, optionnelle)
├── adapters/            # un module par type de boutique (interface commune)
│   ├── base.py          #   ShopAdapter + ProductResult
│   ├── shopify.py       #   JSON-first
│   ├── html.py          #   sélecteurs CSS configurables
│   ├── blocked.py       #   échec propre (sites protégés)
│   └── registry.py      #   type -> classe
├── reference/           # cote de référence (manual / zebradex), cache + historique
├── notifications/       # discord, telegram, dispatch
├── core/
│   ├── stock.py         # classification stock + waiting rooms
│   ├── alerts.py        # seuil + stock + anti-spam
│   └── scanner.py       # cycle de scan (robuste, par boutique)
├── scheduler.py         # APScheduler (scan horaire)
├── seed.py              # boutiques de départ
├── web/                 # FastAPI : routes + templates + static (tableau de bord)
└── cli.py / __main__.py # `python -m pokebot serve|scan`
```

**Stack** : Python · FastAPI + Uvicorn · SQLAlchemy/SQLite · APScheduler · httpx · BeautifulSoup ·
rapidfuzz · Pillow/ImageHash · Jinja2 + Chart.js.

**Robustesse** : l'échec d'un site n'interrompt pas le cycle ; chaque échec est enregistré avec sa
raison (bloqué, structure changée, produit introuvable, timeout…) et affiché dans le rapport.

---

## 📄 Licence & usage

Outil personnel de veille tarifaire. Respectez les CGU des sites et de ZebraDex. Pas de revente de
données, pas de contournement de protections, pas d'achat automatisé.
