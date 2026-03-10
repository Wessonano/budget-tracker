# Feature: Phase 2 — Dashboard + Transactions

The following plan should be complete. Validate documentation and codebase patterns before implementing.

## Feature Description

Interface de visualisation complète pour le budget tracker : dashboard mensuel avec graphes Chart.js (donut catégories + ligne de solde), liste des transactions avec filtres, correction manuelle de catégorie avec apprentissage automatique de patterns, et navigation entre les mois.

## User Story

As Arnaud
I want to see a monthly dashboard with category breakdown, balance evolution, and a searchable transaction list
So that I can understand where my money goes and correct any miscategorized transactions

## Problem Statement

Phase 1 parse et stocke les transactions, mais il n'y a aucune visualisation. Arnaud ne peut pas voir ses dépenses par catégorie, ni corriger les erreurs de catégorisation. Le dashboard et la liste des transactions sont les piliers de l'app.

## Solution Statement

Dashboard server-rendered avec Chart.js pour les graphes, liste des transactions filtrable côté client (< 100 tx/mois), correction de catégorie via modal + API POST, et apprentissage automatique (nouveau pattern en DB avec `learned=1`).

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium-High
**Primary Systems Affected**: Frontend (2 templates, 2 JS, CSS), Backend (routes, DB functions), API
**Dependencies**: Chart.js 4 (CDN), aiohttp, Jinja2 (already installed)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `app.py` (lines 1-165) — Why: All existing routes, `_render_import` helper pattern, `db` global, `create_app()` structure
- `db.py` (lines 1-224) — Why: Schema (6 tables), all CRUD functions, `get_transactions(month)` returns JOINed data, `get_categories()`, `get_months()`, `get_import_history()`, `sqlite3.Row` row_factory
- `categorizer.py` (lines 1-44) — Why: `categorize_transaction()` uses `montant` param, patterns have `category_name` field, "Transfert interne" special case
- `parser.py` (lines 1-196) — Why: Reference only — `parse_boursobank()` return structure has `solde_initial` and `solde_final`
- `templates/base.html` (lines 1-23) — Why: Nav structure, `active` variable, Dashboard/Transactions currently `<span class="nav-link disabled">`
- `templates/import.html` (lines 1-48) — Why: Template pattern (extends base.html, blocks, alert classes)
- `static/css/style.css` (lines 1-110) — Why: CSS variables (--bg, --bg-card, --accent, etc.), existing classes, responsive breakpoint at 600px
- `.claude/PRD.md` (lines 52-58, 189-204, 282-302, 409-442) — Why: Dashboard specs, category patterns, API routes, E2E tests T2.1-T2.7

### New Files to Create

```
static/js/charts.js          # Chart.js initialization (donut + line)
static/js/app.js             # Month nav, filtering, category correction
templates/dashboard.html      # Dashboard page (charts + stats + month nav)
templates/transactions.html   # Transaction list (filters + category correction modal)
```

### Relevant Documentation

- [Chart.js Doughnut](https://www.chartjs.org/docs/latest/charts/doughnut.html) — Donut chart config
- [Chart.js Line](https://www.chartjs.org/docs/latest/charts/line.html) — Line chart for balance evolution
- [aiohttp routing](https://docs.aiohttp.org/en/stable/web_quickstart.html#variable-resources) — `{id}` path variable syntax

### Patterns to Follow

**Naming**: snake_case Python, kebab-case CSS classes, camelCase JS.

**Route handlers** (from app.py):
```python
async def handler(request):
    data = get_something(db)
    return aiohttp_jinja2.render_template('template.html', request, {'active': 'page', ...})
```

**DB functions** (from db.py):
```python
def get_something(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("SELECT ... ORDER BY ...").fetchall()
    return [dict(r) for r in rows]
```

**Template extends** (from import.html):
```html
{% extends "base.html" %}
{% block title %}Page — Budget Tracker{% endblock %}
{% block content %}...{% endblock %}
```

**API JSON response** (from app.py):
```python
return web.json_response({'key': value})
```

**Amount format in DB**: float (negative=debit, positive=credit). Display: `|montant|` with sign indicator.

---

## IMPLEMENTATION PLAN

### Phase 1: Database Layer (db.py)

Add new CRUD and aggregation functions needed for dashboard and category correction. No schema changes needed.

### Phase 2: Backend Routes (app.py)

Add dashboard page handler, transactions page handler, category update API. Change `GET /` from redirect to dashboard.

### Phase 3: Templates (dashboard.html, transactions.html, base.html update)

Server-rendered pages with Chart.js canvas containers and interactive elements.

### Phase 4: Styling (style.css)

Extend dark theme with dashboard layout, cards, badges, chart containers, modal, transaction table.

### Phase 5: JavaScript (charts.js, app.js)

Chart.js rendering, month navigation, client-side filtering, category correction modal.

### Phase 6: Testing & Validation

Manual + curl tests, E2E specs T2.1-T2.7.

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `db.py` — Add Phase 2 functions

**IMPLEMENT**:

Add these functions after the existing CRUD section (after line 224):

```python
def get_transaction_by_id(db: sqlite3.Connection, tx_id: int) -> dict | None:
    """Get a single transaction with category info."""
    row = db.execute(
        """SELECT t.*, c.name as category_name, c.icon as category_icon, c.color as category_color
           FROM transactions t
           LEFT JOIN categories c ON t.category_id = c.id
           WHERE t.id = ?""",
        (tx_id,),
    ).fetchone()
    return dict(row) if row else None


def update_transaction_category(db: sqlite3.Connection, tx_id: int, category_id: int):
    """Update a transaction's category."""
    db.execute(
        "UPDATE transactions SET category_id = ? WHERE id = ?",
        (category_id, tx_id),
    )
    db.commit()


def insert_learned_pattern(db: sqlite3.Connection, category_id: int, pattern: str):
    """Insert a learned pattern from manual category correction.
    Priority 100 = higher than defaults (0), so learned patterns match first.
    """
    # Avoid duplicate patterns
    existing = db.execute(
        "SELECT id FROM category_patterns WHERE pattern = ? AND category_id = ?",
        (pattern, category_id),
    ).fetchone()
    if existing:
        return
    db.execute(
        "INSERT INTO category_patterns (category_id, pattern, priority, learned) VALUES (?, ?, 100, 1)",
        (category_id, pattern),
    )
    db.commit()


def get_month_summary(db: sqlite3.Connection, month: str) -> dict:
    """Get aggregated data for a month: totals by category, overall stats."""
    # Category spending (debits only, grouped)
    rows = db.execute(
        """SELECT c.id, c.name, c.icon, c.color,
                  COALESCE(SUM(CASE WHEN t.montant < 0 THEN ABS(t.montant) ELSE 0 END), 0) as total_debit,
                  COALESCE(SUM(CASE WHEN t.montant > 0 THEN t.montant ELSE 0 END), 0) as total_credit
           FROM categories c
           LEFT JOIN transactions t ON t.category_id = c.id
                AND strftime('%Y-%m', t.date_operation) = ?
           GROUP BY c.id
           ORDER BY c.sort_order""",
        (month,),
    ).fetchall()
    categories = [dict(r) for r in rows]

    # Overall stats
    stats_row = db.execute(
        """SELECT
              COALESCE(SUM(CASE WHEN montant < 0 THEN ABS(montant) ELSE 0 END), 0) as total_depenses,
              COALESCE(SUM(CASE WHEN montant > 0 THEN montant ELSE 0 END), 0) as total_revenus,
              COUNT(*) as tx_count
           FROM transactions
           WHERE strftime('%Y-%m', date_operation) = ?""",
        (month,),
    ).fetchone()

    # Solde from import
    import_row = db.execute(
        "SELECT * FROM imports WHERE period_start LIKE ? OR period_end LIKE ? ORDER BY created_at DESC LIMIT 1",
        (f"%-{month.split('-')[1]}-%", f"%-{month.split('-')[1]}-%"),
    ).fetchone()

    return {
        'categories': categories,
        'total_depenses': stats_row['total_depenses'] if stats_row else 0,
        'total_revenus': stats_row['total_revenus'] if stats_row else 0,
        'tx_count': stats_row['tx_count'] if stats_row else 0,
    }


def get_daily_balances(db: sqlite3.Connection, month: str, solde_initial: float) -> list[dict]:
    """Get daily cumulative balance for line chart."""
    rows = db.execute(
        """SELECT date_operation, SUM(montant) as day_total
           FROM transactions
           WHERE strftime('%Y-%m', date_operation) = ?
           GROUP BY date_operation
           ORDER BY date_operation""",
        (month,),
    ).fetchall()
    balances = []
    balance = solde_initial
    for row in rows:
        balance += row['day_total']
        balances.append({'date': row['date_operation'], 'balance': round(balance, 2)})
    return balances


def get_solde_initial(db: sqlite3.Connection, month: str) -> float | None:
    """Get solde_initial from import matching this month.
    Strategy: find import whose period overlaps with the month.
    """
    # Try to find import matching this month
    rows = db.execute(
        """SELECT t.montant FROM transactions t
           JOIN imports i ON t.import_id = i.id
           WHERE strftime('%Y-%m', t.date_operation) = ?
           ORDER BY t.date_operation ASC LIMIT 1""",
        (month,),
    ).fetchone()
    if not rows:
        return None

    # Get the import for transactions in this month
    import_row = db.execute(
        """SELECT DISTINCT i.id, i.period_start, i.period_end
           FROM imports i
           JOIN transactions t ON t.import_id = i.id
           WHERE strftime('%Y-%m', t.date_operation) = ?
           LIMIT 1""",
        (month,),
    ).fetchone()
    if not import_row:
        return None

    # The solde_initial is not stored in imports table — it's in the parser result
    # but not persisted. We need to store it. For now, calculate from transactions.
    # total_month = sum of all montants for this month
    total = db.execute(
        "SELECT COALESCE(SUM(montant), 0) as total FROM transactions WHERE strftime('%Y-%m', date_operation) = ?",
        (month,),
    ).fetchone()
    # We can't reconstruct solde_initial without storing it.
    # TODO: store solde_initial/solde_final in imports table (schema migration)
    return None


def get_top_expenses(db: sqlite3.Connection, month: str, limit: int = 5) -> list[dict]:
    """Get top N expenses (largest debits) for the month."""
    rows = db.execute(
        """SELECT t.*, c.name as category_name, c.icon as category_icon, c.color as category_color
           FROM transactions t
           LEFT JOIN categories c ON t.category_id = c.id
           WHERE strftime('%Y-%m', t.date_operation) = ? AND t.montant < 0
           ORDER BY t.montant ASC
           LIMIT ?""",
        (month, limit),
    ).fetchall()
    return [dict(r) for r in rows]
```

**GOTCHA**: `solde_initial` and `solde_final` from the parser are NOT stored in the imports table. The schema has `period_start`, `period_end`, `transaction_count` but NOT soldes. We need a schema migration to add `solde_initial REAL` and `solde_final REAL` to the `imports` table.

**ADD to SCHEMA** (in the SCHEMA string, inside the `imports` CREATE TABLE):
```sql
-- After transaction_count:
    solde_initial REAL,
    solde_final REAL,
```

**ADD migration** in `init_db()` after `db.executescript(SCHEMA)`:
```python
# Migration: add solde columns to imports (Phase 2)
try:
    db.execute("ALTER TABLE imports ADD COLUMN solde_initial REAL")
    db.execute("ALTER TABLE imports ADD COLUMN solde_final REAL")
    db.commit()
except sqlite3.OperationalError:
    pass  # Columns already exist
```

**UPDATE `insert_import()`** to accept and store solde_initial and solde_final.

**UPDATE `get_solde_initial()`** to actually read from DB:
```python
def get_solde_initial(db: sqlite3.Connection, month: str) -> float | None:
    row = db.execute(
        """SELECT i.solde_initial FROM imports i
           JOIN transactions t ON t.import_id = i.id
           WHERE strftime('%Y-%m', t.date_operation) = ?
           LIMIT 1""",
        (month,),
    ).fetchone()
    return row['solde_initial'] if row and row['solde_initial'] is not None else None
```

- **VALIDATE**: `cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker && source venv/bin/activate && python3 -c "from db import init_db, get_month_summary, get_daily_balances, get_top_expenses; db = init_db('./test_data'); print('Phase 2 DB OK')" && rm -rf test_data`

### Task 2: UPDATE `app.py` — Add solde storage in import flow

**IMPLEMENT**:

Update the `insert_import` call in `import_upload()` to pass `solde_initial` and `solde_final`:

In `import_upload()`, change the insert_import call (around line 87):
```python
import_id = insert_import(
    db,
    filename,
    sha256,
    result.get("period_start"),
    result.get("period_end"),
    len(transactions),
    result.get("solde_initial"),
    result.get("solde_final"),
)
```

Update `insert_import` in `db.py` to accept and store the new fields:
```python
def insert_import(
    db: sqlite3.Connection,
    filename: str,
    sha256: str,
    period_start: str | None,
    period_end: str | None,
    count: int,
    solde_initial: float | None = None,
    solde_final: float | None = None,
) -> int:
    cur = db.execute(
        "INSERT INTO imports (filename, sha256, period_start, period_end, transaction_count, solde_initial, solde_final) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (filename, sha256, period_start, period_end, count, solde_initial, solde_final),
    )
    db.commit()
    return cur.lastrowid
```

**GOTCHA**: Existing imports in DB won't have solde values. The `get_solde_initial()` function handles this with a None check. If the user re-imports the same PDF, the dedup check blocks it. To populate soldes for existing imports, user needs to delete `data/budget.db` and re-import.

- **VALIDATE**: `source venv/bin/activate && python3 -m py_compile app.py && python3 -m py_compile db.py`

### Task 3: UPDATE `app.py` — Add dashboard and transactions routes

**IMPLEMENT**:

Add these imports at the top of app.py (after existing imports):
```python
from db import (
    ...existing imports...,
    get_transaction_by_id,
    update_transaction_category,
    insert_learned_pattern,
    get_month_summary,
    get_daily_balances,
    get_solde_initial,
    get_top_expenses,
)
```

Replace `dashboard_redirect()` with:
```python
async def dashboard_page(request):
    """GET / — Dashboard mensuel."""
    months = get_months(db)
    month = request.query.get('month')
    if not month:
        month = months[0] if months else None

    if not month:
        return aiohttp_jinja2.render_template(
            'dashboard.html', request,
            {'active': 'dashboard', 'month': None, 'months': months}
        )

    summary = get_month_summary(db, month)
    solde_initial = get_solde_initial(db, month)
    daily_balances = get_daily_balances(db, month, solde_initial or 0)
    top_expenses = get_top_expenses(db, month)
    transactions = get_transactions(db, month)

    return aiohttp_jinja2.render_template(
        'dashboard.html', request,
        {
            'active': 'dashboard',
            'month': month,
            'months': months,
            'summary': summary,
            'solde_initial': solde_initial,
            'daily_balances': daily_balances,
            'top_expenses': top_expenses,
            'transactions': transactions,
        }
    )
```

Add transactions page handler:
```python
async def transactions_page(request):
    """GET /transactions — Liste des transactions."""
    months = get_months(db)
    month = request.query.get('month')
    if not month:
        month = months[0] if months else None

    transactions = get_transactions(db, month) if month else []
    categories = get_categories(db)

    return aiohttp_jinja2.render_template(
        'transactions.html', request,
        {
            'active': 'transactions',
            'month': month,
            'months': months,
            'transactions': transactions,
            'categories': categories,
        }
    )
```

Add category update API:
```python
async def api_update_category(request):
    """POST /api/transactions/{id}/category — Change category + learn pattern."""
    tx_id = int(request.match_info['id'])
    data = await request.json()
    new_category_id = data.get('category_id')

    if not new_category_id:
        return web.json_response({'ok': False, 'error': 'category_id required'}, status=400)

    tx = get_transaction_by_id(db, tx_id)
    if not tx:
        return web.json_response({'ok': False, 'error': 'Transaction not found'}, status=404)

    # Update category
    update_transaction_category(db, tx_id, new_category_id)

    # Learn pattern: extract significant part of libellé
    # Use the cleaned libellé (remove CARTE XX/XX/XX prefix, CB*XXXX suffix)
    libelle = tx['libelle']
    pattern = _extract_pattern(libelle)
    if pattern:
        insert_learned_pattern(db, new_category_id, pattern)

    # Return updated transaction
    updated_tx = get_transaction_by_id(db, tx_id)
    return web.json_response({
        'ok': True,
        'transaction': updated_tx,
    })


def _extract_pattern(libelle: str) -> str | None:
    """Extract a reusable pattern from a transaction libellé.

    Examples:
    - 'CARTE 30/01/26 AGENALINE CB*0403' → 'AGENALINE'
    - 'VIR Virement depuis BoursoBank M LARRIEU ERICK' → 'LARRIEU ERICK'
    - 'PRLV FREE MOBILE' → 'FREE MOBILE'
    """
    import re
    clean = libelle.upper()
    # Remove CARTE DD/MM/YY prefix
    clean = re.sub(r'CARTE\s+\d{2}/\d{2}/\d{2,4}\s+', '', clean)
    # Remove CB*XXXX suffix
    clean = re.sub(r'\s*CB\*\d+', '', clean)
    # Remove VIR/PRLV/VIR INST prefixes
    clean = re.sub(r'^(VIR INST|VIR|PRLV)\s+', '', clean)
    # Remove "Virement depuis BoursoBank" / generic bank phrases
    clean = re.sub(r'VIREMENT DEPUIS BOURSOBANK\s*', '', clean)
    # Remove Ref lines
    clean = re.sub(r'R[ÈE]F\s*:.*', '', clean)
    clean = clean.strip()
    # Must be at least 3 chars to be a useful pattern
    if len(clean) < 3:
        return None
    return clean
```

Update `create_app()` routes — replace the existing route registrations:
```python
app.router.add_get('/', dashboard_page)
app.router.add_get('/transactions', transactions_page)
# ... existing routes (import, api_dashboard, api_months)
app.router.add_post('/api/transactions/{id}/category', api_update_category)
```

**GOTCHA**: aiohttp uses `{id}` syntax for path params (not `<id>` like Flask). Access via `request.match_info['id']`.

- **VALIDATE**: `source venv/bin/activate && python3 -m py_compile app.py`

### Task 4: UPDATE `templates/base.html` — Enable nav + add Chart.js CDN

**IMPLEMENT**:

Replace the full file:

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
        <a href="/" class="nav-logo">Budget Tracker</a>
        <div class="nav-links">
            <a href="/" class="nav-link {% if active == 'dashboard' %}active{% endif %}">Dashboard</a>
            <a href="/transactions" class="nav-link {% if active == 'transactions' %}active{% endif %}">Transactions</a>
            <a href="/import" class="nav-link {% if active == 'import' %}active{% endif %}">Import</a>
        </div>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

**Changes**:
- Dashboard and Transactions are now `<a>` links (not disabled `<span>`)
- Dashboard link is first (primary page)
- Added Chart.js CDN before closing `</body>`
- Added `{% block scripts %}` for page-specific JS

- **VALIDATE**: `cat templates/base.html | grep 'chart.js'`

### Task 5: CREATE `templates/dashboard.html` — Dashboard page

**IMPLEMENT**:

```html
{% extends "base.html" %}
{% block title %}Dashboard — Budget Tracker{% endblock %}
{% block content %}

{% if not month %}
<div class="empty-state">
    <span class="empty-icon">📊</span>
    <h2>Aucune donnee</h2>
    <p>Importez un releve BoursoBank pour commencer.</p>
    <a href="/import" class="btn btn-primary">Importer un releve</a>
</div>
{% else %}

<!-- Month navigation -->
<div class="month-nav">
    <button class="btn btn-icon" id="prev-month" title="Mois precedent">&larr;</button>
    <h1 class="month-title" id="current-month">{{ month }}</h1>
    <button class="btn btn-icon" id="next-month" title="Mois suivant">&rarr;</button>
</div>

<!-- Stats cards -->
<div class="stats-grid">
    <div class="stat-card">
        <span class="stat-label">Depenses</span>
        <span class="stat-value expense">{{ "%.2f"|format(summary.total_depenses) }} &euro;</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Revenus</span>
        <span class="stat-value income">{{ "%.2f"|format(summary.total_revenus) }} &euro;</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Solde initial</span>
        <span class="stat-value">{{ "%.2f"|format(solde_initial) if solde_initial is not none else "—" }} &euro;</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Transactions</span>
        <span class="stat-value">{{ summary.tx_count }}</span>
    </div>
</div>

<!-- Charts -->
<div class="charts-grid">
    <div class="chart-card">
        <h2>Depenses par categorie</h2>
        <div class="chart-container">
            <canvas id="category-donut"></canvas>
        </div>
    </div>
    <div class="chart-card">
        <h2>Evolution du solde</h2>
        <div class="chart-container">
            <canvas id="balance-line"></canvas>
        </div>
    </div>
</div>

<!-- Top expenses -->
{% if top_expenses %}
<div class="card">
    <h2>Top depenses</h2>
    <div class="top-expenses">
        {% for tx in top_expenses %}
        <div class="top-expense-row">
            <span class="tx-category-badge" style="color: {{ tx.category_color }}">{{ tx.category_icon }}</span>
            <span class="tx-libelle">{{ tx.libelle[:50] }}</span>
            <span class="tx-amount expense">{{ "%.2f"|format(tx.montant|abs) }} &euro;</span>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}

{% endif %}
{% endblock %}

{% block scripts %}
{% if month %}
<script src="/static/js/charts.js"></script>
<script>
    // Data from server
    const MONTHS = {{ months | tojson }};
    const CURRENT_MONTH = "{{ month }}";
    const CATEGORY_DATA = {{ summary.categories | tojson }};
    const DAILY_BALANCES = {{ daily_balances | tojson }};

    // Init charts
    document.addEventListener('DOMContentLoaded', function() {
        initCategoryDonut('category-donut', CATEGORY_DATA);
        initBalanceLine('balance-line', DAILY_BALANCES);
        initMonthNav(MONTHS, CURRENT_MONTH);
    });
</script>
{% endif %}
{% endblock %}
```

- **VALIDATE**: `cat templates/dashboard.html | head -5`

### Task 6: CREATE `templates/transactions.html` — Transactions page

**IMPLEMENT**:

```html
{% extends "base.html" %}
{% block title %}Transactions — Budget Tracker{% endblock %}
{% block content %}

{% if not month %}
<div class="empty-state">
    <span class="empty-icon">📋</span>
    <h2>Aucune donnee</h2>
    <p>Importez un releve BoursoBank pour voir vos transactions.</p>
    <a href="/import" class="btn btn-primary">Importer un releve</a>
</div>
{% else %}

<!-- Month navigation -->
<div class="month-nav">
    <button class="btn btn-icon" id="prev-month" title="Mois precedent">&larr;</button>
    <h1 class="month-title" id="current-month">{{ month }}</h1>
    <button class="btn btn-icon" id="next-month" title="Mois suivant">&rarr;</button>
</div>

<!-- Filters -->
<div class="filter-bar">
    <select id="filter-category" class="filter-select">
        <option value="">Toutes les categories</option>
        {% for cat in categories %}
        <option value="{{ cat.id }}">{{ cat.icon }} {{ cat.name }}</option>
        {% endfor %}
    </select>
    <input type="text" id="filter-search" class="filter-input" placeholder="Rechercher...">
</div>

<!-- Transactions table -->
<div class="table-wrapper">
<table class="table transaction-table" id="tx-table">
    <thead>
        <tr>
            <th>Date</th>
            <th>Libelle</th>
            <th class="text-right">Montant</th>
            <th>Categorie</th>
        </tr>
    </thead>
    <tbody>
        {% for tx in transactions %}
        <tr class="tx-row" data-id="{{ tx.id }}" data-category="{{ tx.category_id }}" data-libelle="{{ tx.libelle|lower }}">
            <td class="tx-date">{{ tx.date_operation }}</td>
            <td class="tx-libelle">{{ tx.libelle[:60] }}</td>
            <td class="text-right {{ 'income' if tx.montant > 0 else 'expense' }}">
                {{ "+" if tx.montant > 0 else "" }}{{ "%.2f"|format(tx.montant) }} &euro;
            </td>
            <td>
                <button class="category-badge" data-tx-id="{{ tx.id }}" data-current-cat="{{ tx.category_id }}"
                        style="border-color: {{ tx.category_color }}; color: {{ tx.category_color }}">
                    {{ tx.category_icon }} {{ tx.category_name }}
                </button>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
</div>

<p class="tx-count" id="tx-count">{{ transactions|length }} transactions</p>

<!-- Category correction modal -->
<div class="modal-overlay" id="modal-overlay" style="display:none">
    <div class="modal">
        <h3>Changer la categorie</h3>
        <p class="modal-tx-info" id="modal-tx-info"></p>
        <select id="modal-category-select" class="filter-select">
            {% for cat in categories %}
            <option value="{{ cat.id }}">{{ cat.icon }} {{ cat.name }}</option>
            {% endfor %}
        </select>
        <div class="modal-actions">
            <button class="btn btn-secondary" id="modal-cancel">Annuler</button>
            <button class="btn btn-primary" id="modal-save">Enregistrer</button>
        </div>
    </div>
</div>

{% endif %}
{% endblock %}

{% block scripts %}
{% if month %}
<script src="/static/js/app.js"></script>
<script>
    const MONTHS = {{ months | tojson }};
    const CURRENT_MONTH = "{{ month }}";
    const PAGE = 'transactions';

    document.addEventListener('DOMContentLoaded', function() {
        initMonthNav(MONTHS, CURRENT_MONTH);
        initFilters();
        initCategoryCorrection();
    });
</script>
{% endif %}
{% endblock %}
```

- **VALIDATE**: `cat templates/transactions.html | head -5`

### Task 7: UPDATE `static/css/style.css` — Phase 2 styling

**IMPLEMENT**:

Add after the existing content (after the `@media` block at line 110):

```css
/* ===== Phase 2 — Dashboard & Transactions ===== */

/* Month navigation */
.month-nav {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    margin-bottom: 2rem;
}
.month-title {
    font-size: 1.5rem;
    margin: 0;
    min-width: 140px;
    text-align: center;
}
.btn-icon {
    background: var(--bg-card);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.5rem 1rem;
    cursor: pointer;
    font-size: 1.2rem;
}
.btn-icon:hover { border-color: var(--accent); color: var(--accent); }
.btn-icon:disabled { opacity: 0.3; cursor: not-allowed; }

/* Stats grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}
.stat-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}
.stat-label { color: var(--text-muted); font-size: 0.85rem; }
.stat-value { font-size: 1.5rem; font-weight: 700; }
.stat-value.expense { color: var(--error); }
.stat-value.income { color: var(--success); }

/* Charts grid */
.charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 2rem;
}
.chart-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
}
.chart-card h2 { font-size: 1rem; margin-bottom: 1rem; color: var(--text-muted); }
.chart-container { position: relative; width: 100%; max-height: 300px; }

/* Card generic */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.card h2 { font-size: 1rem; margin-bottom: 1rem; color: var(--text-muted); }

/* Top expenses */
.top-expenses { display: flex; flex-direction: column; gap: 0.75rem; }
.top-expense-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.top-expense-row .tx-libelle { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.top-expense-row .tx-amount { font-weight: 600; white-space: nowrap; }

/* Empty state */
.empty-state {
    text-align: center;
    padding: 4rem 1rem;
}
.empty-icon { font-size: 4rem; display: block; margin-bottom: 1rem; }
.empty-state h2 { margin-bottom: 0.5rem; }
.empty-state p { color: var(--text-muted); margin-bottom: 1.5rem; }

/* Filter bar */
.filter-bar {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
}
.filter-select, .filter-input {
    background: var(--bg-card);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    font-size: 0.9rem;
}
.filter-select:focus, .filter-input:focus {
    outline: none;
    border-color: var(--accent);
}
.filter-input { flex: 1; min-width: 150px; }

/* Transaction table enhancements */
.transaction-table .tx-date { white-space: nowrap; color: var(--text-muted); font-size: 0.9rem; }
.transaction-table .tx-libelle {
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.text-right { text-align: right; }
.income { color: var(--success); }
.expense { color: var(--error); }

/* Category badge (clickable) */
.category-badge {
    background: transparent;
    border: 1px solid;
    border-radius: 20px;
    padding: 0.25rem 0.75rem;
    font-size: 0.8rem;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.2s;
}
.category-badge:hover { background: rgba(255,255,255,0.05); }

.tx-count { color: var(--text-muted); font-size: 0.85rem; margin-top: 1rem; }

/* Modal */
.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}
.modal {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 2rem;
    min-width: 320px;
    max-width: 90vw;
}
.modal h3 { margin-bottom: 1rem; }
.modal-tx-info { color: var(--text-muted); margin-bottom: 1rem; font-size: 0.9rem; }
.modal-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.5rem; }
.btn-secondary {
    background: var(--bg-input);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.5rem 1.5rem;
    cursor: pointer;
}
.btn-secondary:hover { border-color: var(--text-muted); }

/* Toast notification */
.toast {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    background: var(--bg-card);
    border: 1px solid var(--success);
    border-radius: 8px;
    padding: 0.75rem 1.5rem;
    color: var(--success);
    z-index: 1001;
    animation: toast-in 0.3s ease;
}
.toast.error { border-color: var(--error); color: var(--error); }
@keyframes toast-in { from { opacity: 0; transform: translateY(1rem); } to { opacity: 1; transform: none; } }

/* Responsive overrides for Phase 2 */
@media (max-width: 800px) {
    .charts-grid { grid-template-columns: 1fr; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
    .stats-grid { grid-template-columns: 1fr; }
    .filter-bar { flex-direction: column; }
    .transaction-table .tx-libelle { max-width: 150px; }
    .modal { min-width: auto; margin: 1rem; }
}
```

**GOTCHA**: The existing `.container` max-width is 900px. For 2-column charts grid, consider increasing to `max-width: 1100px` in the `.container` rule (line 44). Update:

```css
.container { max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }
```

- **VALIDATE**: `wc -l static/css/style.css` (should be > 250 lines)

### Task 8: CREATE `static/js/charts.js` — Chart.js rendering

**IMPLEMENT**:

```javascript
/**
 * Chart.js initialization for Budget Tracker dashboard.
 */

function initCategoryDonut(canvasId, categories) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // Filter categories with actual spending
    const data = categories
        .filter(c => c.total_debit > 0)
        .sort((a, b) => b.total_debit - a.total_debit);

    if (data.length === 0) {
        canvas.parentElement.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">Aucune depense</p>';
        return;
    }

    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: data.map(c => c.icon + ' ' + c.name),
            datasets: [{
                data: data.map(c => c.total_debit),
                backgroundColor: data.map(c => c.color),
                borderWidth: 0,
                hoverOffset: 8,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '55%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#e0e0e0',
                        padding: 12,
                        usePointStyle: true,
                        pointStyleWidth: 10,
                        font: { size: 12 },
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = ((ctx.raw / total) * 100).toFixed(1);
                            return ctx.label + ': ' + ctx.raw.toFixed(2) + ' € (' + pct + '%)';
                        }
                    }
                }
            }
        }
    });
}


function initBalanceLine(canvasId, dailyBalances) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (!dailyBalances || dailyBalances.length === 0) {
        canvas.parentElement.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">Pas de donnees</p>';
        return;
    }

    // Format dates for display (YYYY-MM-DD → DD/MM)
    const labels = dailyBalances.map(d => {
        const parts = d.date.split('-');
        return parts[2] + '/' + parts[1];
    });

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Solde',
                data: dailyBalances.map(d => d.balance),
                borderColor: '#e94560',
                backgroundColor: 'rgba(233, 69, 96, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 3,
                pointHoverRadius: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                x: {
                    ticks: { color: '#888', maxTicksLimit: 10 },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    ticks: {
                        color: '#888',
                        callback: function(v) { return v.toFixed(0) + ' €'; }
                    },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) { return 'Solde: ' + ctx.raw.toFixed(2) + ' €'; }
                    }
                }
            }
        }
    });
}
```

- **VALIDATE**: `cat static/js/charts.js | head -5`

### Task 9: CREATE `static/js/app.js` — Interactivity

**IMPLEMENT**:

```javascript
/**
 * Budget Tracker — Interactive features.
 * Month navigation, transaction filtering, category correction.
 */

// ===== Month Navigation =====

function initMonthNav(months, currentMonth) {
    const prevBtn = document.getElementById('prev-month');
    const nextBtn = document.getElementById('next-month');
    const titleEl = document.getElementById('current-month');

    if (!prevBtn || !nextBtn || !titleEl) return;

    // Format month for display
    titleEl.textContent = formatMonth(currentMonth);

    const idx = months.indexOf(currentMonth);
    prevBtn.disabled = idx >= months.length - 1;
    nextBtn.disabled = idx <= 0;

    prevBtn.addEventListener('click', function() {
        if (idx < months.length - 1) navigateMonth(months[idx + 1]);
    });
    nextBtn.addEventListener('click', function() {
        if (idx > 0) navigateMonth(months[idx - 1]);
    });
}

function navigateMonth(month) {
    const url = new URL(window.location);
    url.searchParams.set('month', month);
    window.location.href = url.toString();
}

function formatMonth(yyyymm) {
    const [y, m] = yyyymm.split('-');
    const names = ['', 'Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin',
                   'Juillet', 'Aout', 'Septembre', 'Octobre', 'Novembre', 'Decembre'];
    return names[parseInt(m)] + ' ' + y;
}


// ===== Transaction Filtering =====

function initFilters() {
    const catFilter = document.getElementById('filter-category');
    const searchFilter = document.getElementById('filter-search');
    if (!catFilter && !searchFilter) return;

    function applyFilters() {
        const catId = catFilter ? catFilter.value : '';
        const search = searchFilter ? searchFilter.value.toLowerCase() : '';
        const rows = document.querySelectorAll('.tx-row');
        let visible = 0;

        rows.forEach(function(row) {
            const matchCat = !catId || row.dataset.category === catId;
            const matchSearch = !search || row.dataset.libelle.includes(search);
            row.style.display = (matchCat && matchSearch) ? '' : 'none';
            if (matchCat && matchSearch) visible++;
        });

        const countEl = document.getElementById('tx-count');
        if (countEl) countEl.textContent = visible + ' transaction' + (visible !== 1 ? 's' : '');
    }

    if (catFilter) catFilter.addEventListener('change', applyFilters);
    if (searchFilter) searchFilter.addEventListener('input', applyFilters);
}


// ===== Category Correction =====

let selectedTxId = null;

function initCategoryCorrection() {
    const overlay = document.getElementById('modal-overlay');
    const cancelBtn = document.getElementById('modal-cancel');
    const saveBtn = document.getElementById('modal-save');
    const catSelect = document.getElementById('modal-category-select');
    const txInfo = document.getElementById('modal-tx-info');

    if (!overlay) return;

    // Open modal on category badge click
    document.querySelectorAll('.category-badge').forEach(function(badge) {
        badge.addEventListener('click', function() {
            selectedTxId = this.dataset.txId;
            const row = this.closest('.tx-row');
            const libelle = row ? row.querySelector('.tx-libelle').textContent : '';
            txInfo.textContent = libelle;
            catSelect.value = this.dataset.currentCat;
            overlay.style.display = 'flex';
        });
    });

    // Close modal
    cancelBtn.addEventListener('click', function() {
        overlay.style.display = 'none';
        selectedTxId = null;
    });
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.style.display = 'none';
            selectedTxId = null;
        }
    });

    // Save category
    saveBtn.addEventListener('click', function() {
        if (!selectedTxId) return;
        const newCatId = catSelect.value;
        saveBtn.disabled = true;
        saveBtn.textContent = '...';

        fetch('/api/transactions/' + selectedTxId + '/category', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category_id: parseInt(newCatId) }),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.ok) {
                // Update row in table
                const badge = document.querySelector('.category-badge[data-tx-id="' + selectedTxId + '"]');
                if (badge && data.transaction) {
                    badge.innerHTML = data.transaction.category_icon + ' ' + data.transaction.category_name;
                    badge.style.borderColor = data.transaction.category_color;
                    badge.style.color = data.transaction.category_color;
                    badge.dataset.currentCat = data.transaction.category_id;
                    // Update row data attribute for filtering
                    const row = badge.closest('.tx-row');
                    if (row) row.dataset.category = data.transaction.category_id;
                }
                showToast('Categorie mise a jour');
            } else {
                showToast('Erreur: ' + (data.error || 'unknown'), true);
            }
        })
        .catch(function(err) {
            showToast('Erreur reseau', true);
        })
        .finally(function() {
            overlay.style.display = 'none';
            selectedTxId = null;
            saveBtn.disabled = false;
            saveBtn.textContent = 'Enregistrer';
        });
    });
}


// ===== Toast Notification =====

function showToast(message, isError) {
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' error' : '');
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 3000);
}
```

- **VALIDATE**: `cat static/js/app.js | head -5`

### Task 10: Verify all files compile and lint

**VALIDATE**:

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
source venv/bin/activate
python3 -m py_compile app.py
python3 -m py_compile db.py
python3 -m py_compile categorizer.py
python3 -m py_compile parser.py
echo "All Python files compile OK"
```

### Task 11: Integration test — Start server and verify routes

**VALIDATE**:

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
source venv/bin/activate

# Clean slate for testing
rm -rf test_integration_data
DATA_DIR=./test_integration_data python3 -c "
from db import init_db
db = init_db('./test_integration_data')
print('DB initialized with', len(db.execute('SELECT * FROM categories').fetchall()), 'categories')
print('Solde columns:', 'solde_initial' in [d[0] for d in db.execute('PRAGMA table_info(imports)').fetchall()])
"
rm -rf test_integration_data
```

### Task 12: Run parser tests to ensure no regression

**VALIDATE**:

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
source venv/bin/activate
python3 tests/test_parser.py
```

### Task 13: Full integration test with server

**VALIDATE**:

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
source venv/bin/activate

# Start server in background
DATA_DIR=./test_data python3 app.py &
SERVER_PID=$!
sleep 2

# Test dashboard (empty state)
curl -s http://localhost:8080/ | grep "Aucune donnee" && echo "✅ Empty dashboard OK" || echo "❌ Dashboard FAIL"

# Test import page
curl -s http://localhost:8080/import | grep "Importer" && echo "✅ Import page OK" || echo "❌ Import FAIL"

# Upload PDF
curl -s -F "file=@tests/sample-boursobank.pdf" http://localhost:8080/import | grep "transactions importees" && echo "✅ Upload OK" || echo "❌ Upload FAIL"

# Test dashboard with data
curl -s "http://localhost:8080/?month=2026-02" | grep "category-donut" && echo "✅ Dashboard with data OK" || echo "❌ Dashboard data FAIL"

# Test transactions page
curl -s "http://localhost:8080/transactions?month=2026-02" | grep "tx-table" && echo "✅ Transactions OK" || echo "❌ Transactions FAIL"

# Test API
curl -s "http://localhost:8080/api/dashboard?month=2026-02" | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ API OK:', len(d.get('transactions',[])), 'tx')" || echo "❌ API FAIL"

# Test months API
curl -s "http://localhost:8080/api/months" | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Months:', d.get('months',[]))" || echo "❌ Months FAIL"

# Cleanup
kill $SERVER_PID 2>/dev/null
rm -rf test_data
```

### Task 14: COMMIT + PUSH

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
git add -A
git commit -m "feat: Phase 2 — Dashboard + Transactions + category correction"
git push
```

- **VALIDATE**: `git log --oneline -1`

---

## TESTING STRATEGY

### Unit Tests (no new test file needed for Phase 2 — DB functions are tested via integration)

- Parser tests unchanged (tests/test_parser.py)
- DB functions verified via integration tests (curl + Python oneliners)

### Integration Tests (manual + curl)

- Server start → dashboard loads (empty state)
- Upload PDF → dashboard shows data
- Transactions page with filters
- Category correction via API POST
- Month navigation

### Edge Cases

- Empty month (no transactions) → "Aucune donnée" state
- Month with only credits (no debits) → donut empty, line chart shows balance
- Category correction to same category → no-op (still creates pattern)
- Very long libellé → CSS text-overflow ellipsis
- Multiple corrections on same transaction → each creates a pattern

---

## VALIDATION COMMANDS

### Level 1: Syntax

```bash
source venv/bin/activate
python3 -m py_compile app.py
python3 -m py_compile db.py
python3 -m py_compile categorizer.py
python3 -m py_compile parser.py
```

### Level 2: Unit Tests

```bash
python3 tests/test_parser.py
```

### Level 3: Integration

```bash
# Start server with test data, upload PDF, check all pages
# (see Task 13 for full script)
```

### Level 4: E2E (agent-browser)

See PRD section 13, tests T2.1 to T2.7.

---

## ACCEPTANCE CRITERIA

- [ ] `GET /` renders dashboard with donut chart and balance line chart
- [ ] Dashboard shows stats cards (dépenses, revenus, solde initial, nb transactions)
- [ ] Dashboard shows top 5 expenses
- [ ] Empty month shows "Aucune donnée" with link to import
- [ ] Month navigation (prev/next) works
- [ ] `GET /transactions` renders filterable transaction list
- [ ] Category filter works (client-side)
- [ ] Text search filter works (client-side)
- [ ] Category badge click opens correction modal
- [ ] Category correction saves via `POST /api/transactions/{id}/category`
- [ ] Correction creates learned pattern in DB (`learned=1`, `priority=100`)
- [ ] Transaction row updates in-place after correction (no page reload)
- [ ] All existing Phase 1 functionality still works (import, dedup, parser)
- [ ] Dark theme consistent across all pages
- [ ] Mobile responsive (375px) — no horizontal scroll
- [ ] Chart.js renders correctly (canvas not empty)

---

## COMPLETION CHECKLIST

- [ ] db.py: new functions (get_transaction_by_id, update_transaction_category, insert_learned_pattern, get_month_summary, get_daily_balances, get_solde_initial, get_top_expenses)
- [ ] db.py: schema migration (solde_initial, solde_final in imports)
- [ ] db.py: insert_import updated with solde params
- [ ] app.py: dashboard_page handler (replaces redirect)
- [ ] app.py: transactions_page handler
- [ ] app.py: api_update_category handler
- [ ] app.py: _extract_pattern helper
- [ ] templates/base.html: nav enabled, Chart.js CDN, scripts block
- [ ] templates/dashboard.html: full dashboard page
- [ ] templates/transactions.html: full transactions page with modal
- [ ] static/css/style.css: ~150 lines of Phase 2 styles
- [ ] static/js/charts.js: donut + line chart functions
- [ ] static/js/app.js: month nav + filters + category correction
- [ ] Parser tests still pass (no regression)
- [ ] Integration test passes (server start → upload → dashboard → transactions)
- [ ] Commit + push

---

## NOTES

- **No new Python dependencies** — Chart.js loaded via CDN, all Python deps already installed.
- **Solde migration** — The imports table needs `solde_initial` and `solde_final` columns. Added via `ALTER TABLE` in `init_db()` with try/except for idempotency. Existing imports won't have values; user should delete `data/budget.db` and re-import to populate.
- **Client-side filtering** — Chosen over server-side for simplicity (< 100 tx/month). If performance becomes an issue in the future, move to SQL-based filtering.
- **Pattern extraction** — `_extract_pattern()` cleans the libellé (removes CARTE prefix, CB* suffix, VIR prefix) to create a reusable pattern. This ensures "CARTE 30/01/26 AGENALINE CB*0403" generates pattern "AGENALINE", not the full string.
- **Months are DESC in API** — `get_months()` returns most recent first. Navigation: prev = higher index (older), next = lower index (newer).
- **Chart.js v4 CDN** — Using `https://cdn.jsdelivr.net/npm/chart.js@4` (no SRI hash for simplicity). In production Phase 4, consider self-hosting.
- **The `get_solde_initial` function** relies on the migration. If DB has no solde data, the balance line chart will start at 0. Not ideal but functional. Re-import fixes it.
