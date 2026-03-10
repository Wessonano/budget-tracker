# Feature: Phase 1 — Foundation + Parser

The following plan should be complete. Validate documentation and codebase patterns before implementing.

## Feature Description

Setup complet du projet budget-tracker : serveur aiohttp, base SQLite, parser PDF BoursoBank, auto-catégorisation, page d'import avec upload et feedback. C'est le socle sur lequel les phases suivantes (dashboard, enveloppes, partage) seront construites.

## User Story

As Arnaud
I want to upload my BoursoBank PDF bank statement
So that my transactions are automatically extracted, categorized, and stored in a database

## Problem Statement

Arnaud reçoit ses relevés BoursoBank en PDF. Il n'a aucune visibilité structurée sur ses dépenses. Il faut extraire les transactions automatiquement pour alimenter le budget tracker.

## Solution Statement

Parser le PDF avec `pdftotext -layout` (colonnes alignées), extraire les transactions par regex, les catégoriser automatiquement via patterns, et stocker le tout en SQLite. Interface web d'upload avec feedback immédiat.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: Backend (parser, DB, server), Frontend (page import)
**Dependencies**: aiohttp, aiohttp-jinja2, pdftotext (poppler-utils)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `CLAUDE.md` — Architecture, stack, DB schema, code patterns, conventions
- `.claude/PRD.md` — Requirements complets, catégories, user stories, E2E tests
- `tests/sample-boursobank-layout.txt` — Output exact de `pdftotext -layout` sur un vrai relevé BoursoBank. **C'EST LA RÉFÉRENCE pour écrire le parser.** 118 lignes, 2 pages, ~30 transactions.
- `tests/sample-boursobank.pdf` — Le PDF original pour les tests d'intégration

### New Files to Create

```
budget-tracker/
├── app.py                  # Serveur aiohttp, routes, startup
├── parser.py               # Parsing PDF BoursoBank
├── categorizer.py          # Auto-catégorisation par patterns
├── db.py                   # SQLite init + requêtes
├── requirements.txt        # Dépendances Python
├── .env.example            # Template config
├── .gitignore              # uploads/, data/, .env, __pycache__
├── static/
│   └── css/style.css       # Dark theme minimal (pour la page import)
├── templates/
│   ├── base.html           # Layout commun
│   └── import.html         # Page upload + feedback
└── tests/
    ├── test_parser.py      # Tests unitaires du parser
    └── sample-boursobank-layout.txt  # (déjà copié)
```

### Relevant Documentation

- [aiohttp server docs](https://docs.aiohttp.org/en/stable/web.html) — Routes, request handling, file upload
- [aiohttp-jinja2](https://aiohttp-jinja2.readthedocs.io/) — Template rendering setup
- [pdftotext man page](https://linux.die.net/man/1/pdftotext) — Flag `-layout` preserve column positions
- [Chart.js](https://www.chartjs.org/docs/latest/) — Pour Phase 2, pas besoin maintenant

### Patterns to Follow

**Naming**: snake_case pour fichiers Python et fonctions. kebab-case pour CSS.

**Error Handling (parser)**:
```python
def parse_boursobank(pdf_path: str) -> dict:
    """Returns {'ok': True, 'transactions': [...], 'period': {...}, 'solde_initial': float, 'solde_final': float}
    or {'ok': False, 'error': 'description'}"""
```

**Montants**:
- PDF : format français `1 234,56` (espace = séparateur milliers, virgule = décimale)
- DB : float (négatif = débit, positif = crédit)
- Conversion : supprimer espaces, remplacer virgule par point, `float()`

**DB**: Requêtes SQLite directes, pas d'ORM. Fonctions async dans db.py.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (db.py, requirements.txt, .env.example, .gitignore)

Setup base : dépendances, config, base de données SQLite avec schema complet.

### Phase 2: Core — Parser (parser.py)

Le cœur du projet. Parser le texte `pdftotext -layout` avec des regex pour extraire chaque transaction, le solde initial/final, la période.

### Phase 3: Core — Categorizer (categorizer.py)

Matcher chaque transaction avec une catégorie via des patterns regex stockés en DB.

### Phase 4: Server + UI (app.py, templates/, static/)

Serveur aiohttp avec route d'upload, parsing automatique, feedback utilisateur.

### Phase 5: Tests (tests/test_parser.py)

Tests unitaires sur le parser avec le sample réel.

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `requirements.txt`

```
aiohttp>=3.9
aiohttp-jinja2>=1.6
aiofiles>=23.0
python-dotenv>=1.0
```

- **VALIDATE**: `cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

### Task 2: CREATE `.env.example`

```env
# Server
PORT=8080
HOST=0.0.0.0
DATA_DIR=./data

# Discord alerts (Phase 3)
DISCORD_WEBHOOK_BUDGET=

# Share token (Phase 3)
SHARE_TOKEN=
```

- **VALIDATE**: `cat .env.example`

### Task 3: CREATE `.gitignore`

```
__pycache__/
*.pyc
venv/
.env
data/
uploads/
*.db
.DS_Store
```

- **VALIDATE**: `cat .gitignore`

### Task 4: CREATE `db.py` — Database layer

**IMPLEMENT**:

1. `init_db(data_dir)` — Crée le dossier data/ et initialise SQLite avec le schema complet (6 tables : imports, transactions, categories, category_patterns, budgets, settings).

2. `seed_categories(db)` — Insère les catégories par défaut si la table est vide :

| name | icon | color | sort_order |
|------|------|-------|------------|
| Courses | 🛒 | #4CAF50 | 1 |
| Bar / Tabac | ☕ | #FF9800 | 2 |
| Abonnements tech | 🤖 | #2196F3 | 3 |
| Téléphone | 📱 | #9C27B0 | 4 |
| Internet | 📡 | #00BCD4 | 5 |
| Shopping | 📦 | #E91E63 | 6 |
| Famille | 👨‍👩‍👧 | #FF5722 | 7 |
| Transfert interne | 🔄 | #607D8B | 8 |
| Remboursement | ↩️ | #8BC34A | 9 |
| Divers | 📌 | #9E9E9E | 10 |

3. `seed_patterns(db)` — Insère les patterns par défaut pour chaque catégorie (voir PRD section 7.3).

4. Fonctions CRUD :
   - `get_import_by_hash(db, sha256) -> dict|None`
   - `insert_import(db, filename, sha256, period_start, period_end, count) -> int`
   - `insert_transactions(db, import_id, transactions: list[dict]) -> int`
   - `get_categories(db) -> list[dict]`
   - `get_patterns(db) -> list[dict]` — Retourne tous les patterns triés par priority DESC
   - `get_transactions(db, month: str) -> list[dict]` — Filtre par mois (YYYY-MM), JOIN categories
   - `get_months(db) -> list[str]` — Liste des mois distincts avec données
   - `get_import_history(db) -> list[dict]` — Liste des imports

**SCHEMA SQL** (copier exactement depuis CLAUDE.md section Database Schema) :

```sql
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    sha256 TEXT UNIQUE NOT NULL,
    period_start TEXT,
    period_end TEXT,
    transaction_count INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    import_id INTEGER REFERENCES imports(id),
    date_operation TEXT NOT NULL,
    date_valeur TEXT,
    libelle TEXT NOT NULL,
    montant REAL NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    icon TEXT NOT NULL,
    color TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS category_patterns (
    id INTEGER PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id),
    pattern TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    learned INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id),
    amount_max REAL NOT NULL,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

**IMPORTANT** : Utiliser `sqlite3` standard (pas aiosqlite). Les opérations DB sont rapides, pas besoin d'async pour SQLite. Encapsuler dans `run_in_executor` côté aiohttp si nécessaire.

- **VALIDATE**: `source venv/bin/activate && python3 -c "from db import init_db; db = init_db('./test_data'); print('OK')" && rm -rf test_data`

### Task 5: CREATE `parser.py` — BoursoBank PDF parser

**IMPLEMENT**:

C'est le fichier le plus critique. Lire `tests/sample-boursobank-layout.txt` **EN ENTIER** avant de coder.

**Fonction principale** : `parse_boursobank(pdf_path: str) -> dict`

1. Appeler `subprocess.run(['pdftotext', '-layout', pdf_path, '-'], capture_output=True, text=True)` pour obtenir le texte.

2. Parser le texte ligne par ligne. Voici la structure exacte du layout :

**Format d'une ligne de transaction** (regex) :
```
^(\d{2}/\d{2}/\d{4})\s+(.+?)\s{2,}(\d{2}/\d{2}/\d{4})\s+([\d\s]+,\d{2})?\s*([\d\s]+,\d{2})?$
```

Mais attention, c'est plus subtil que ça. Analyser le sample :

**Ligne de transaction standard** (ex ligne 32 du sample) :
```
02/02/2026 CARTE 30/01/26 AGENALINE                     CB*0403                                              02/02/2026                  11,50
```
- Position 0-9 : date_operation (DD/MM/YYYY)
- Position 11+ : libellé (jusqu'aux espaces multiples avant date_valeur)
- Ensuite : date_valeur (DD/MM/YYYY)
- Ensuite : montant débit OU crédit (positionné à droite)

**Ligne indentée** (ex ligne 33) :
```
02/02/2026      CARTE 31/01/26 INTERMARCHE AGENT CB*0403                                                     02/02/2026                  32,70
```
- Même format, la date est là mais avec des espaces supplémentaires après. C'est une transaction normale, pas une ligne de continuation.

**Ligne de continuation** (ex lignes 45-46 après ligne 44) :
```
10/02/2026 VIR Virement depuis BoursoBank                                                                    10/02/2026                  31,00
                M LARRIEU ERICK
                Rèf : SCT406182026021000630794303
```
- Les lignes de continuation commencent par des espaces (pas de date en position 0-9)
- Elles complètent le libellé de la transaction précédente
- Il faut les concaténer au libellé parent

**Ligne SOLDE AU** (ex ligne 27) :
```
                                                                                             SOLDE AU : 30/01/2026                                            111,19
```
- Extraire le montant comme solde initial

**Ligne Nouveau solde** (ex ligne 100) :
```
                                Nouveau solde en EUR :                                                                                                        107,52
```
- Extraire le montant comme solde final

**Ligne de période** (ex ligne 17) :
```
28/02/2026 40618 80360     00040362117                        23        EUR       du 31/01/2026 au 27/02/2026
```
- Extraire les dates de début et fin de période

**Algorithme de parsing** :

```python
def parse_boursobank(pdf_path: str) -> dict:
    # 1. Exécuter pdftotext -layout
    result = subprocess.run(['pdftotext', '-layout', pdf_path, '-'],
                          capture_output=True, text=True)
    if result.returncode != 0:
        return {'ok': False, 'error': f'pdftotext failed: {result.stderr}'}

    text = result.stdout
    lines = text.split('\n')

    transactions = []
    current_tx = None
    solde_initial = None
    solde_final = None
    period_start = None
    period_end = None

    for line in lines:
        # Skip lignes vides, headers, footers
        stripped = line.strip()
        if not stripped:
            continue
        if any(skip in stripped for skip in ['MOUVEMENTS EN EUR', 'Libellé', 'opération',
               'réception', 'approbation', 'Boursorama', 'Traversière', 'Clientèle',
               'médiateur', 'B.I.C.', 'Mod.', 'Montant', 'N° de RIB', 'Banque Guichet',
               'Extrait de votre', 'Protégé par', 'BOURSOBANK', 'M LARRIEU ARNAUD',
               'RUE DE', 'APPARTEMENT', 'frais bancaires']):
            continue

        # Période
        period_match = re.search(r'du (\d{2}/\d{2}/\d{4}) au (\d{2}/\d{2}/\d{4})', line)
        if period_match:
            period_start = convert_date(period_match.group(1))
            period_end = convert_date(period_match.group(2))
            continue

        # SOLDE AU
        if 'SOLDE AU' in line:
            amount_match = re.search(r'([\d\s]+,\d{2})\s*$', line)
            if amount_match:
                solde_initial = parse_amount(amount_match.group(1))
            continue

        # Nouveau solde
        if 'Nouveau solde' in line:
            amount_match = re.search(r'([\d\s]+,\d{2})\s*$', line)
            if amount_match:
                solde_final = parse_amount(amount_match.group(1))
            continue

        # Transaction line (starts with date DD/MM/YYYY)
        tx_match = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.+)', line)
        if tx_match:
            # Sauver la transaction précédente
            if current_tx:
                transactions.append(current_tx)

            date_op = tx_match.group(1)
            rest = tx_match.group(2)

            # Extraire date_valeur et montants depuis la fin de la ligne
            # Pattern: ... DD/MM/YYYY    amount    amount?
            parts = parse_transaction_line(rest)

            current_tx = {
                'date_operation': convert_date(date_op),
                'date_valeur': parts['date_valeur'],
                'libelle': parts['libelle'].strip(),
                'montant': parts['montant'],  # négatif=débit, positif=crédit
            }
            continue

        # Continuation line (starts with spaces, no date)
        if current_tx and not re.match(r'^\d{2}/\d{2}/\d{4}', line) and stripped:
            # Vérifier que c'est vraiment une continuation (pas un header/footer)
            # Les continuations contiennent du texte utile (nom, ref)
            current_tx['libelle'] += ' ' + stripped
            continue

    # Dernière transaction
    if current_tx:
        transactions.append(current_tx)

    if not transactions:
        return {'ok': False, 'error': 'Aucune transaction trouvée dans le PDF'}

    return {
        'ok': True,
        'transactions': transactions,
        'period_start': period_start,
        'period_end': period_end,
        'solde_initial': solde_initial,
        'solde_final': solde_final,
        'count': len(transactions),
    }
```

**Fonctions helper** :

```python
def convert_date(date_fr: str) -> str:
    """DD/MM/YYYY -> YYYY-MM-DD"""
    parts = date_fr.split('/')
    return f"{parts[2]}-{parts[1]}-{parts[0]}"

def parse_amount(raw: str) -> float:
    """'1 234,56' -> 1234.56"""
    return float(raw.replace(' ', '').replace(',', '.'))

def parse_transaction_line(rest: str) -> dict:
    """Parse everything after the date_operation.

    La difficulté : le libellé est de longueur variable, suivi d'espaces multiples,
    puis date_valeur, puis débit ou crédit.

    Stratégie : chercher le pattern date + montants depuis la fin de la ligne.
    """
    # Chercher date_valeur (DD/MM/YYYY) suivie de montant(s)
    match = re.search(
        r'(\d{2}/\d{2}/\d{4})\s+([\d\s]+,\d{2})(?:\s+([\d\s]+,\d{2}))?\s*$',
        rest
    )
    if match:
        date_valeur = convert_date(match.group(1))
        # Tout ce qui est avant le match = libellé
        libelle = rest[:match.start()].strip()

        amount1 = parse_amount(match.group(2))
        amount2 = parse_amount(match.group(3)) if match.group(3) else None

        # Déterminer débit vs crédit
        # S'il y a 2 montants : le 1er est débit, le 2e est crédit
        # S'il y a 1 seul montant : sa position (colonne) détermine débit/crédit
        # Heuristique simple : si le montant est après beaucoup d'espaces après date_valeur
        # et qu'il est très à droite → crédit. Sinon → débit.
        #
        # Meilleure approche : compter les espaces entre date_valeur et le montant.
        # Débit est juste après date_valeur (~20 chars).
        # Crédit est beaucoup plus loin (~40 chars).
        if amount2 is not None:
            # 2 montants = débit + crédit (rare mais possible)
            montant = amount2 - amount1
        else:
            # 1 montant : vérifier la position dans la ligne originale
            # Le montant crédit est positionné plus à droite que le débit
            amount_pos = match.start(2) + len(rest) - len(rest)
            # Compter les espaces entre date_valeur et le montant
            after_date = rest[match.end(1):]
            spaces_before_amount = len(after_date) - len(after_date.lstrip())

            if spaces_before_amount > 30:
                # Crédit (très à droite)
                montant = amount1
            else:
                # Débit
                montant = -amount1

        return {
            'date_valeur': date_valeur,
            'libelle': libelle,
            'montant': montant,
        }

    # Fallback : pas de pattern trouvé
    return {
        'date_valeur': None,
        'libelle': rest.strip(),
        'montant': 0.0,
    }
```

**GOTCHA CRITIQUE — Débit vs Crédit** : La seule façon fiable de distinguer débit et crédit est la **position du montant dans la ligne**. Dans le layout BoursoBank :
- **Débit** : montant positionné à ~colonne 90-105 (juste après date_valeur + ~20 espaces)
- **Crédit** : montant positionné à ~colonne 115-130 (beaucoup plus à droite, après ~40 espaces)

La meilleure approche est de mesurer la position absolue du montant dans la ligne complète (pas juste `rest`). Il faut donc passer la ligne complète à `parse_transaction_line` ou mesurer autrement.

**Approche recommandée** : Utiliser la position absolue dans la ligne originale. Les montants débit sont dans la zone colonne 90-110, les crédits dans la zone 110+. Mesurer la position du premier chiffre du montant dans la ligne originale.

Concrètement, en regardant le sample :
```
02/02/2026 VIR INST M LARRIEU ARNAUD                                                                         02/02/2026                                      100,00
```
Le "100,00" crédit commence vers la colonne 134.

```
02/02/2026 CARTE 30/01/26 AGENALINE                     CB*0403                                              02/02/2026                  11,50
```
Le "11,50" débit commence vers la colonne 113.

**Méthode la plus robuste** : passer la `full_line` et chercher les montants par position absolue. Seuil à ~colonne 125 : avant = débit, après = crédit.

- **VALIDATE**: `source venv/bin/activate && python3 -c "from parser import parse_boursobank; r = parse_boursobank('tests/sample-boursobank.pdf'); print(f'OK: {r[\"count\"]} transactions') if r['ok'] else print(f'FAIL: {r[\"error\"]}')" `

### Task 6: CREATE `categorizer.py` — Auto-catégorisation

**IMPLEMENT**:

```python
import re
import sqlite3

def categorize_transaction(libelle: str, patterns: list[dict]) -> int | None:
    """Match un libellé contre les patterns, retourne category_id ou None (=Divers).

    patterns: list de {'pattern': str, 'category_id': int, 'priority': int}
    triés par priority DESC (les patterns learned en premier).
    """
    libelle_upper = libelle.upper()
    for p in patterns:
        if re.search(p['pattern'], libelle_upper, re.IGNORECASE):
            return p['category_id']
    return None  # fallback = Divers

def categorize_transactions(transactions: list[dict], db: sqlite3.Connection) -> list[dict]:
    """Catégorise toutes les transactions. Retourne les transactions avec category_id ajouté."""
    from db import get_patterns, get_categories

    patterns = get_patterns(db)
    categories = get_categories(db)

    # Trouver l'id de "Divers" (fallback)
    divers_id = next((c['id'] for c in categories if c['name'] == 'Divers'), None)

    for tx in transactions:
        cat_id = categorize_transaction(tx['libelle'], patterns)
        tx['category_id'] = cat_id if cat_id is not None else divers_id

    return transactions
```

**Patterns par défaut** (insérés par `seed_patterns` dans db.py) :

```python
DEFAULT_PATTERNS = [
    # (category_name, pattern_regex, priority)
    ('Courses', 'INTERMARCHE', 0),
    ('Courses', 'AGENALINE', 0),
    ('Courses', 'LECLERC', 0),
    ('Courses', 'CARREFOUR', 0),
    ('Courses', 'LIDL', 0),
    ('Courses', 'ALDI', 0),
    ('Bar / Tabac', 'LE BALTO', 0),
    ('Bar / Tabac', 'TABAC', 0),
    ('Bar / Tabac', 'MAISON DU PERO', 0),
    ('Bar / Tabac', 'CAFE', 0),
    ('Abonnements tech', 'CLAUDE\\.AI', 0),
    ('Abonnements tech', 'PROTON', 0),
    ('Abonnements tech', 'GOOGLE.*CLOUD', 0),
    ('Abonnements tech', 'Google Play', 0),
    ('Abonnements tech', 'GANDI', 0),
    ('Téléphone', 'FREE MOBILE', 0),
    ('Téléphone', 'SFR', 0),
    ('Téléphone', 'ORANGE', 0),
    ('Téléphone', 'BOUYGUES', 0),
    ('Internet', r'FREE\b(?!.*MOBILE)', 0),
    ('Shopping', 'AMAZON', 0),
    ('Shopping', 'PAYPAL', 0),
    ('Famille', 'LARRIEU ERICK', 0),
    ('Famille', 'ELISA LARRIEU', 0),
    ('Famille', 'CASTAING MARTINE', 0),
    ('Transfert interne', 'VIR INST M LARRIEU ARNAUD', 0),
    ('Remboursement', 'AVOIR', 0),
]
```

**GOTCHA** : Le pattern "Transfert interne" ne doit matcher que les **crédits** (montant > 0). Si c'est un débit, c'est un virement sortant → catégorie "Famille" ou "Divers". Gérer ça dans `categorize_transaction` en ajoutant le montant au contexte.

- **VALIDATE**: `source venv/bin/activate && python3 -c "from categorizer import categorize_transaction; print(categorize_transaction('CARTE INTERMARCHE AGENT', [{'pattern': 'INTERMARCHE', 'category_id': 1, 'priority': 0}]))"`

### Task 7: CREATE `templates/base.html` — Layout commun

**IMPLEMENT**: Template Jinja2 avec :
- `<!DOCTYPE html>` + meta viewport (responsive)
- Lien vers `/static/css/style.css`
- Nav simple : Import | (Dashboard et Transactions grisés "Phase 2")
- Block `{% block title %}` et `{% block content %}`
- Dark theme via CSS

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Budget Tracker{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <nav class="main-nav">
        <a href="/" class="nav-logo">💰 Budget Tracker</a>
        <div class="nav-links">
            <a href="/import" class="nav-link {% if active == 'import' %}active{% endif %}">Import</a>
            <span class="nav-link disabled">Dashboard</span>
            <span class="nav-link disabled">Transactions</span>
        </div>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- **VALIDATE**: `cat templates/base.html | head -5`

### Task 8: CREATE `templates/import.html` — Page upload

**IMPLEMENT**: Extends base.html. Contient :

1. **Zone d'upload** : formulaire `<form method="post" enctype="multipart/form-data" action="/import">` avec `<input type="file" accept=".pdf">` et bouton "Importer".

2. **Feedback** (si `result` est passé au template) :
   - Succès : "✅ {count} transactions importées — Période {period_start} → {period_end} — Solde : {solde_initial}€ → {solde_final}€"
   - Erreur : "❌ {error}" (doublon, fichier invalide, parsing échoué)

3. **Historique des imports** : tableau simple (date, fichier, nb transactions, période)

```html
{% extends "base.html" %}
{% block title %}Import — Budget Tracker{% endblock %}
{% block content %}
<h1>Importer un relevé BoursoBank</h1>

{% if result %}
<div class="alert {{ 'alert-success' if result.ok else 'alert-error' }}">
    {% if result.ok %}
    ✅ {{ result.count }} transactions importées<br>
    Période : {{ result.period_start }} → {{ result.period_end }}<br>
    Solde : {{ result.solde_initial }}€ → {{ result.solde_final }}€
    {% else %}
    ❌ {{ result.error }}
    {% endif %}
</div>
{% endif %}

<form method="post" action="/import" enctype="multipart/form-data" class="upload-form">
    <label for="pdf-file" class="upload-zone" id="drop-zone">
        <span class="upload-icon">📄</span>
        <span class="upload-text">Cliquer ou glisser un PDF BoursoBank</span>
        <input type="file" id="pdf-file" name="file" accept=".pdf" required>
    </label>
    <button type="submit" class="btn btn-primary">Importer</button>
</form>

{% if imports %}
<h2>Historique des imports</h2>
<table class="table">
    <thead>
        <tr><th>Date</th><th>Fichier</th><th>Transactions</th><th>Période</th></tr>
    </thead>
    <tbody>
        {% for imp in imports %}
        <tr>
            <td>{{ imp.created_at[:10] }}</td>
            <td>{{ imp.filename }}</td>
            <td>{{ imp.transaction_count }}</td>
            <td>{{ imp.period_start }} → {{ imp.period_end }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endif %}
{% endblock %}
```

- **VALIDATE**: `cat templates/import.html | head -5`

### Task 9: CREATE `static/css/style.css` — Dark theme

**IMPLEMENT**: Dark theme minimaliste, cohérent avec l'écosystème nanoserveur.

```css
:root {
    --bg: #1a1a2e;
    --bg-card: #16213e;
    --bg-input: #0f3460;
    --text: #e0e0e0;
    --text-muted: #888;
    --accent: #e94560;
    --accent-hover: #ff6b6b;
    --success: #4CAF50;
    --error: #f44336;
    --border: #2a2a4a;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
}

.main-nav {
    display: flex; justify-content: space-between; align-items: center;
    padding: 1rem 2rem; background: var(--bg-card); border-bottom: 1px solid var(--border);
}
.nav-logo { color: var(--text); text-decoration: none; font-size: 1.2rem; font-weight: bold; }
.nav-links { display: flex; gap: 1.5rem; }
.nav-link { color: var(--text-muted); text-decoration: none; }
.nav-link.active { color: var(--accent); }
.nav-link.disabled { opacity: 0.3; cursor: not-allowed; }

.container { max-width: 900px; margin: 2rem auto; padding: 0 1rem; }

h1 { margin-bottom: 1.5rem; }
h2 { margin: 2rem 0 1rem; }

.alert { padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; }
.alert-success { background: rgba(76, 175, 80, 0.15); border: 1px solid var(--success); }
.alert-error { background: rgba(244, 67, 54, 0.15); border: 1px solid var(--error); }

.upload-form { margin: 1.5rem 0; }
.upload-zone {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 3rem; border: 2px dashed var(--border); border-radius: 12px;
    cursor: pointer; transition: border-color 0.2s;
    background: var(--bg-card);
}
.upload-zone:hover { border-color: var(--accent); }
.upload-icon { font-size: 3rem; margin-bottom: 0.5rem; }
.upload-text { color: var(--text-muted); }
.upload-zone input[type="file"] { display: none; }

.btn { padding: 0.75rem 2rem; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; margin-top: 1rem; }
.btn-primary { background: var(--accent); color: white; }
.btn-primary:hover { background: var(--accent-hover); }

.table { width: 100%; border-collapse: collapse; }
.table th, .table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
.table th { color: var(--text-muted); font-weight: 500; }

@media (max-width: 600px) {
    .main-nav { flex-direction: column; gap: 0.5rem; }
    .container { padding: 0 0.5rem; }
    .upload-zone { padding: 2rem 1rem; }
}
```

- **VALIDATE**: `cat static/css/style.css | wc -l` (devrait être > 50 lignes)

### Task 10: CREATE `app.py` — Serveur aiohttp

**IMPLEMENT**:

```python
import os
import hashlib
import aiohttp_jinja2
import jinja2
from aiohttp import web
from dotenv import load_dotenv

from db import init_db, get_import_by_hash, insert_import, insert_transactions, get_import_history
from parser import parse_boursobank
from categorizer import categorize_transactions

load_dotenv()

DATA_DIR = os.getenv('DATA_DIR', './data')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
PORT = int(os.getenv('PORT', 8080))
HOST = os.getenv('HOST', '0.0.0.0')

db = None

async def import_page(request):
    """GET /import — Page d'upload avec historique"""
    imports = get_import_history(db)
    return aiohttp_jinja2.render_template('import.html', request,
                                           {'active': 'import', 'imports': imports})

async def import_upload(request):
    """POST /import — Upload + parse PDF"""
    reader = await request.multipart()
    field = await reader.next()

    if not field or field.name != 'file':
        return aiohttp_jinja2.render_template('import.html', request,
            {'active': 'import', 'result': {'ok': False, 'error': 'Aucun fichier envoyé'},
             'imports': get_import_history(db)})

    filename = field.filename
    if not filename or not filename.lower().endswith('.pdf'):
        return aiohttp_jinja2.render_template('import.html', request,
            {'active': 'import', 'result': {'ok': False, 'error': 'Le fichier doit être un PDF'},
             'imports': get_import_history(db)})

    # Lire le contenu
    data = await field.read()

    if len(data) > 5 * 1024 * 1024:  # 5 Mo max
        return aiohttp_jinja2.render_template('import.html', request,
            {'active': 'import', 'result': {'ok': False, 'error': 'Fichier trop volumineux (max 5 Mo)'},
             'imports': get_import_history(db)})

    # Hash pour déduplication
    sha256 = hashlib.sha256(data).hexdigest()
    if get_import_by_hash(db, sha256):
        return aiohttp_jinja2.render_template('import.html', request,
            {'active': 'import', 'result': {'ok': False, 'error': 'Ce relevé a déjà été importé'},
             'imports': get_import_history(db)})

    # Sauver le PDF
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    pdf_path = os.path.join(UPLOAD_DIR, f"{sha256}.pdf")
    with open(pdf_path, 'wb') as f:
        f.write(data)

    # Parser
    result = parse_boursobank(pdf_path)
    if not result['ok']:
        os.remove(pdf_path)  # Cleanup
        return aiohttp_jinja2.render_template('import.html', request,
            {'active': 'import', 'result': result, 'imports': get_import_history(db)})

    # Catégoriser
    transactions = categorize_transactions(result['transactions'], db)

    # Insérer en DB
    import_id = insert_import(db, filename, sha256,
                               result.get('period_start'), result.get('period_end'),
                               len(transactions))
    insert_transactions(db, import_id, transactions)

    result['filename'] = filename
    return aiohttp_jinja2.render_template('import.html', request,
        {'active': 'import', 'result': result, 'imports': get_import_history(db)})

async def dashboard_redirect(request):
    """GET / — Redirige vers /import pour Phase 1"""
    raise web.HTTPFound('/import')

async def api_dashboard(request):
    """GET /api/dashboard?month=YYYY-MM — Données JSON"""
    from db import get_transactions, get_categories
    month = request.query.get('month')
    if not month:
        # Dernier mois disponible
        from db import get_months
        months = get_months(db)
        month = months[0] if months else None

    if not month:
        return web.json_response({'transactions': [], 'categories': []})

    transactions = get_transactions(db, month)
    categories = get_categories(db)

    return web.json_response({
        'month': month,
        'transactions': transactions,
        'categories': categories,
    })

async def api_months(request):
    """GET /api/months — Liste des mois disponibles"""
    from db import get_months
    return web.json_response({'months': get_months(db)})

def create_app():
    app = web.Application(client_max_size=5 * 1024 * 1024)

    # Jinja2
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('templates'))

    # Static files
    app.router.add_static('/static/', path='static', name='static')

    # Routes
    app.router.add_get('/', dashboard_redirect)
    app.router.add_get('/import', import_page)
    app.router.add_post('/import', import_upload)
    app.router.add_get('/api/dashboard', api_dashboard)
    app.router.add_get('/api/months', api_months)

    return app

if __name__ == '__main__':
    global db
    db = init_db(DATA_DIR)
    app = create_app()
    print(f"Budget Tracker running on http://{HOST}:{PORT}")
    web.run_app(app, host=HOST, port=PORT)
```

**GOTCHA** : Le `global db` est simple mais suffisant pour un usage perso. Pas besoin de pool de connexions pour SQLite.

- **VALIDATE**: `source venv/bin/activate && python3 -c "from app import create_app; print('App created OK')"`

### Task 11: CREATE `tests/test_parser.py` — Tests unitaires

**IMPLEMENT**:

```python
"""Tests du parser BoursoBank sur le sample réel."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import parse_boursobank, parse_amount, convert_date

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), 'sample-boursobank.pdf')


def test_parse_amount():
    assert parse_amount('11,50') == 11.50
    assert parse_amount('1 234,56') == 1234.56
    assert parse_amount('100,00') == 100.00
    assert parse_amount('404,52') == 404.52


def test_convert_date():
    assert convert_date('02/02/2026') == '2026-02-02'
    assert convert_date('31/01/2026') == '2026-01-31'


def test_parse_full_pdf():
    """Test sur le vrai relevé BoursoBank."""
    result = parse_boursobank(SAMPLE_PDF)

    assert result['ok'] is True
    assert result['count'] >= 25  # Au moins 25 transactions
    assert result['period_start'] == '2026-01-31'
    assert result['period_end'] == '2026-02-27'
    assert result['solde_initial'] == 111.19
    assert result['solde_final'] == 107.52

    # Vérifier quelques transactions connues
    txs = result['transactions']

    # VIR INST crédit 100€
    vir_credits = [t for t in txs if 'VIR INST M LARRIEU ARNAUD' in t['libelle'] and t['montant'] > 0]
    assert len(vir_credits) >= 3  # Il y en a plusieurs

    # CARTE AGENALINE débit 11,50€
    agenaline = [t for t in txs if 'AGENALINE' in t['libelle']]
    assert len(agenaline) == 1
    assert agenaline[0]['montant'] == -11.50

    # AVOIR AMAZON crédit 53,35€
    avoir = [t for t in txs if 'AVOIR' in t['libelle'] and 'AMAZON' in t['libelle'] and t['montant'] == 53.35]
    assert len(avoir) >= 1

    # VIR Erick débit 31€ (virement sortant vers Erick)
    erick_debit = [t for t in txs if 'LARRIEU ERICK' in t['libelle'] and t['montant'] < 0]
    assert len(erick_debit) >= 1

    # CLAUDE.AI débit 216€
    claude = [t for t in txs if 'CLAUDE.AI' in t['libelle']]
    assert len(claude) == 1
    assert claude[0]['montant'] == -216.00

    # PAYPAL débit 404,52€
    paypal = [t for t in txs if 'PAYPAL' in t['libelle']]
    assert len(paypal) == 1
    assert paypal[0]['montant'] == -404.52


def test_transactions_have_dates():
    """Toutes les transactions ont des dates valides."""
    result = parse_boursobank(SAMPLE_PDF)
    for tx in result['transactions']:
        assert tx['date_operation'] is not None
        assert len(tx['date_operation']) == 10  # YYYY-MM-DD
        assert tx['date_operation'].startswith('2026-')


def test_multiline_transactions():
    """Les virements multi-lignes ont le nom dans le libellé."""
    result = parse_boursobank(SAMPLE_PDF)
    txs = result['transactions']

    # VIR de Erick doit contenir "LARRIEU ERICK" ou "M LARRIEU ERICK" dans le libellé
    erick_txs = [t for t in txs if 'ERICK' in t['libelle'].upper()]
    assert len(erick_txs) >= 1


if __name__ == '__main__':
    test_parse_amount()
    test_convert_date()
    test_parse_full_pdf()
    test_transactions_have_dates()
    test_multiline_transactions()
    print("✅ All tests passed!")
```

- **VALIDATE**: `source venv/bin/activate && python3 tests/test_parser.py`

### Task 12: COMMIT + PUSH

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
git add -A
git commit -m "feat: Phase 1 — foundation + BoursoBank parser + import UI"
git push
```

- **VALIDATE**: `git log --oneline -1`

---

## TESTING STRATEGY

### Unit Tests (tests/test_parser.py)

- `test_parse_amount` — conversion montants FR → float
- `test_convert_date` — conversion dates FR → ISO
- `test_parse_full_pdf` — parsing complet du sample réel (30+ transactions, soldes, période)
- `test_transactions_have_dates` — toutes les dates sont valides
- `test_multiline_transactions` — les virements multi-lignes sont correctement fusionnés

### Integration Tests (manuels)

- Lancer le serveur, uploader le PDF sample via le navigateur
- Vérifier le feedback (nombre de transactions, période, soldes)
- Re-uploader → vérifier le refus doublon
- Vérifier l'API JSON `/api/dashboard?month=2026-02`

### Edge Cases

- PDF vide ou corrompu → message d'erreur propre
- Fichier non-PDF → rejet avant parsing
- PDF > 5 Mo → rejet
- PDF d'une autre banque → parsing échoue avec message clair

---

## VALIDATION COMMANDS

### Level 1: Syntax

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
source venv/bin/activate
python3 -m py_compile app.py
python3 -m py_compile parser.py
python3 -m py_compile categorizer.py
python3 -m py_compile db.py
```

### Level 2: Unit Tests

```bash
python3 tests/test_parser.py
```

### Level 3: Integration (serveur)

```bash
# Terminal 1: lancer le serveur
python3 app.py &
sleep 2

# Terminal 2: tester l'API
curl -s http://localhost:8080/import | grep "Budget Tracker"
curl -s -F "file=@tests/sample-boursobank.pdf" http://localhost:8080/import | grep "transactions importées"
curl -s http://localhost:8080/api/dashboard?month=2026-02 | python3 -m json.tool | head -20
curl -s http://localhost:8080/api/months | python3 -m json.tool

# Cleanup
kill %1
```

### Level 4: E2E (Phase 1 — agent-browser)

Voir PRD section 13, tests T1.1 à T1.5.

---

## ACCEPTANCE CRITERIA

- [x] `pdftotext -layout` extrait le texte du PDF BoursoBank
- [ ] Le parser extrait >= 25 transactions du sample
- [ ] Solde initial (111,19€) et final (107,52€) correctement extraits
- [ ] Période (2026-01-31 → 2026-02-27) correctement extraite
- [ ] Débits sont négatifs, crédits sont positifs
- [ ] Virements multi-lignes fusionnés (libellé complet)
- [ ] Auto-catégorisation : INTERMARCHE → Courses, CLAUDE.AI → Abonnements tech, etc.
- [ ] Upload via interface web fonctionne
- [ ] Doublon détecté et refusé
- [ ] Fichier non-PDF refusé
- [ ] API `/api/dashboard?month=2026-02` retourne les transactions JSON
- [ ] Dark theme cohérent
- [ ] Tous les tests unitaires passent

---

## COMPLETION CHECKLIST

- [ ] requirements.txt créé + venv installé
- [ ] .env.example + .gitignore créés
- [ ] db.py : schema + seed categories + seed patterns + CRUD
- [ ] parser.py : parse_boursobank() fonctionne sur le sample réel
- [ ] categorizer.py : catégorise automatiquement les transactions
- [ ] templates/base.html + import.html
- [ ] static/css/style.css (dark theme)
- [ ] app.py : serveur aiohttp avec routes import + API
- [ ] tests/test_parser.py : tous les tests passent
- [ ] Commit + push

---

## NOTES

- **pdftotext doit être installé** sur la machine (`brew install poppler` sur macOS, `apt install poppler-utils` sur Debian). Déjà installé sur le Mac Mini.
- **Le parser est le point critique**. La distinction débit/crédit repose sur la position du montant dans la ligne (colonne ~113 = débit, ~134 = crédit). Il faut mesurer ça précisément en regardant le sample.
- **Pas d'async pour SQLite** : sqlite3 est bloquant mais rapide. On peut utiliser `asyncio.to_thread()` si besoin, mais pour un usage perso c'est inutile.
- **Phase 2** construira le dashboard par-dessus cette base. Les routes API (`/api/dashboard`, `/api/months`) sont déjà en place pour préparer.
- Le PDF test est dans `tests/sample-boursobank.pdf` — **NE PAS le committer sur GitHub** (données personnelles). Ajouter `tests/sample-boursobank.pdf` au .gitignore.
