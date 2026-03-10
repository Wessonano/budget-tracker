# Feature: Phase 3 — Enveloppes + Alertes + Partage

The following plan should be complete. Validate documentation and codebase patterns before implementing.

## Feature Description

Phase 3 completes the Budget Tracker MVP with three pillars : (1) Enveloppes budgetaires — CRUD for monthly budget limits per category with colored progress bars, (2) Alertes Discord — webhook notifications when spending reaches 80% or 100% of a budget envelope, (3) Page de partage — a read-only summary page accessible by Arnaud's father via a unique token URL (no login), plus month-to-month comparison on the dashboard.

## User Story

As Arnaud
I want to define budget envelopes per category, get Discord alerts when I approach limits, and share a monthly summary with my father
So that I can actively control my spending, get warned before overspending, and let my father follow my finances without setup

## Problem Statement

Phases 1 & 2 provide visibility (dashboard, transactions) but no active budget management. Arnaud has no spending limits, no alerts, and his father has no way to see the data. Without envelopes and alerts, the tracker is passive. Without the share page, the father needs to ask Arnaud directly.

## Solution Statement

Add budget envelopes (category + max amount) with visual progress bars (green/orange/red), trigger Discord webhook alerts after each import when thresholds are crossed (80% and 100%), create a public share page at `/share/<token>` showing a monthly summary without transaction details, and add a month-to-month comparison section to the dashboard.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium-High
**Primary Systems Affected**: Backend (db.py, app.py, new notifications.py), Frontend (3 new templates, CSS additions, JS additions)
**Dependencies**: aiohttp (already installed), uuid (stdlib), datetime (stdlib)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `app.py` (all) — Why: All existing routes, `_render_import` helper pattern, `db` global, `create_app()` structure. New routes follow same pattern.
- `db.py` (all) — Why: Schema (budgets + settings tables exist but unused), all CRUD patterns, `get_month_summary()` (lines 276-306) for comparison logic, `get_categories()` for dropdown data.
- `categorizer.py` (all) — Why: `categorize_transactions()` is called after import — alerts should be checked at the same point.
- `templates/base.html` (all) — Why: Nav structure — need to add "Enveloppes" link. Chart.js CDN already loaded.
- `templates/dashboard.html` (all) — Why: Add comparison section. Existing pattern for stats cards, chart cards, and month nav.
- `templates/transactions.html` (all) — Why: Modal pattern for category correction — reuse for budget creation/editing.
- `static/css/style.css` (all) — Why: Existing design tokens (vars), card/table/modal patterns. Add progress bar + share page styles.
- `static/js/app.js` (all) — Why: Month nav, modal pattern. Add budget CRUD interactions.
- `static/js/charts.js` (all) — Why: `initCategoryDonut()` — reuse for share page donut.
- `.env.example` — Why: Already has `DISCORD_WEBHOOK_BUDGET` and `SHARE_TOKEN` placeholders.
- `.claude/PRD.md` (sections 7.4-7.6, section 13 T3.1-T3.9) — Why: Exact specs for envelopes, alerts, share page, and E2E test scenarios.

### New Files to Create

- `notifications.py` — Discord webhook alert sending (async with aiohttp.ClientSession)
- `templates/budgets.html` — Envelopes management page (CRUD + progress bars)
- `templates/share.html` — Public read-only monthly summary for father
- `tests/test_budgets.py` — Unit tests for budget CRUD + alert logic

### Relevant Documentation

- [Discord Webhook Execute API](https://discord.com/developers/docs/resources/webhook#execute-webhook)
  - POST with JSON body: `{"content": "...", "embeds": [...]}`
  - Returns 204 No Content on success
  - Why: Format and send budget alerts
- [aiohttp ClientSession](https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession)
  - `session.post(url, json=payload)` for webhook calls
  - Why: Non-blocking HTTP call to Discord
- [Chart.js Doughnut](https://www.chartjs.org/docs/latest/charts/doughnut.html)
  - Why: Reuse on share page for category breakdown

### Patterns to Follow

**Route registration** (app.py `create_app()`):
```python
app.router.add_get("/budgets", budgets_page)
app.router.add_post("/budgets", budgets_create)
app.router.add_post("/api/budgets/{id}/delete", budgets_delete)  # POST not DELETE (HTML forms)
app.router.add_get("/share/{token}", share_page)
```

**DB function pattern** (db.py):
```python
def get_budgets(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("SELECT ... ORDER BY ...").fetchall()
    return [dict(r) for r in rows]
```

**Template rendering** (app.py):
```python
async def budgets_page(request):
    return aiohttp_jinja2.render_template("budgets.html", request, {
        "active": "budgets", "budgets": ..., "categories": ...,
    })
```

**Jinja2 data to JS** (dashboard.html line 83):
```jinja2
const DATA = {{ python_dict | tojson }};
```

**CSS color variables** (style.css):
```css
--success: #4CAF50;  /* green — budget < 60% */
--warning: #FF9800;  /* orange — reuse for 60-80% */
--error: #f44336;    /* red — budget > 80% */
```

**Modal pattern** (transactions.html lines 66-80, app.js lines 77-150):
- Overlay `#modal-overlay` with `display:none` default
- Click badge -> open modal, fill form
- Cancel/save buttons
- Fetch API call on save

---

## IMPLEMENTATION PLAN

### Phase 1: Database Layer (db.py)

Add CRUD functions for budgets table and settings table. Add `get_month_comparison()` function. These are the foundation for all other work.

### Phase 2: Notifications (notifications.py)

Create Discord webhook sender. Implement alert logic: check budgets after import, send webhook for 80% and 100% thresholds.

### Phase 3: Backend Routes (app.py)

Add routes for budgets page (CRUD), share page, and budget alert trigger after import. Wire up notifications.

### Phase 4: Templates & Frontend (templates/, static/)

Create budgets.html (progress bars, create/edit forms), share.html (public summary), update dashboard.html (comparison section), update base.html (nav link). Add CSS for progress bars and share page.

### Phase 5: Tests

Unit tests for budget CRUD, alert formatting, share token validation, month comparison.

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `db.py` — Add settings CRUD

**IMPLEMENT**: Add two functions for the existing `settings` table:

```python
def get_setting(db: sqlite3.Connection, key: str) -> str | None:
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None

def set_setting(db: sqlite3.Connection, key: str, value: str):
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )
    db.commit()
```

- **PATTERN**: Same style as `get_import_by_hash()` at db.py:153
- **VALIDATE**: `cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker && source venv/bin/activate && python3 -c "from db import init_db, get_setting, set_setting; db=init_db('/tmp/test_bt'); set_setting(db,'foo','bar'); assert get_setting(db,'foo')=='bar'; print('OK')" && rm -rf /tmp/test_bt`

### Task 2: UPDATE `db.py` — Add budget CRUD functions

**IMPLEMENT**: Add these functions after the existing Phase 2 functions:

```python
def get_budgets_with_spending(db: sqlite3.Connection, month: str) -> list[dict]:
    """Get all active budgets with current month spending."""
    rows = db.execute(
        """SELECT b.id, b.category_id, b.amount_max, b.active,
                  c.name as category_name, c.icon as category_icon, c.color as category_color,
                  COALESCE(SUM(CASE WHEN t.montant < 0 THEN ABS(t.montant) ELSE 0 END), 0) as spent
           FROM budgets b
           JOIN categories c ON b.category_id = c.id
           LEFT JOIN transactions t ON t.category_id = b.category_id
                AND strftime('%Y-%m', t.date_operation) = ?
           WHERE b.active = 1
           GROUP BY b.id
           ORDER BY c.sort_order""",
        (month,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["percent"] = round((d["spent"] / d["amount_max"]) * 100, 1) if d["amount_max"] > 0 else 0
        result.append(d)
    return result

def insert_budget(db: sqlite3.Connection, category_id: int, amount_max: float) -> int:
    cur = db.execute(
        "INSERT INTO budgets (category_id, amount_max) VALUES (?, ?)",
        (category_id, amount_max),
    )
    db.commit()
    return cur.lastrowid

def update_budget(db: sqlite3.Connection, budget_id: int, amount_max: float):
    db.execute("UPDATE budgets SET amount_max = ? WHERE id = ?", (amount_max, budget_id))
    db.commit()

def delete_budget(db: sqlite3.Connection, budget_id: int):
    db.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
    db.commit()

def get_budget_by_id(db: sqlite3.Connection, budget_id: int) -> dict | None:
    row = db.execute(
        "SELECT b.*, c.name as category_name FROM budgets b JOIN categories c ON b.category_id = c.id WHERE b.id = ?",
        (budget_id,),
    ).fetchone()
    return dict(row) if row else None
```

- **GOTCHA**: The `get_budgets_with_spending` query JOINs transactions filtered by month. If no transactions exist for the month, `spent` will be 0 (thanks to COALESCE + LEFT JOIN).
- **GOTCHA**: A category can have at most 1 active budget. Consider adding a UNIQUE constraint or check before insert. Simpler: check in route handler before inserting.
- **VALIDATE**: `source venv/bin/activate && python3 -c "
from db import init_db, insert_budget, get_budgets_with_spending, delete_budget
db = init_db('/tmp/test_bt')
bid = insert_budget(db, 1, 100.0)
budgets = get_budgets_with_spending(db, '2026-02')
assert len(budgets) == 1
assert budgets[0]['amount_max'] == 100.0
assert budgets[0]['spent'] == 0
assert budgets[0]['percent'] == 0
delete_budget(db, bid)
assert len(get_budgets_with_spending(db, '2026-02')) == 0
print('OK')
" && rm -rf /tmp/test_bt`

### Task 3: UPDATE `db.py` — Add month comparison function

**IMPLEMENT**: Add a function that returns per-category spending deltas between two months.

```python
def get_month_comparison(db: sqlite3.Connection, current_month: str, previous_month: str) -> list[dict]:
    """Compare spending between two months. Returns deltas per category."""
    current = get_month_summary(db, current_month)
    previous = get_month_summary(db, previous_month)

    comparison = []
    prev_map = {c["id"]: c for c in previous["categories"]}
    for cat in current["categories"]:
        prev_cat = prev_map.get(cat["id"], {})
        prev_debit = prev_cat.get("total_debit", 0)
        curr_debit = cat["total_debit"]
        if prev_debit == 0 and curr_debit == 0:
            continue
        delta = curr_debit - prev_debit
        delta_pct = round((delta / prev_debit) * 100, 1) if prev_debit > 0 else None
        comparison.append({
            "id": cat["id"],
            "name": cat["name"],
            "icon": cat["icon"],
            "color": cat["color"],
            "current": curr_debit,
            "previous": prev_debit,
            "delta": delta,
            "delta_pct": delta_pct,
        })
    return comparison
```

**IMPORTS needed**: None extra (uses existing `get_month_summary`).

Helper function for previous month computation (add at top of db.py or in a utils section):

```python
def previous_month(month_str: str) -> str:
    """'2026-02' -> '2026-01', '2026-01' -> '2025-12'"""
    from datetime import datetime, timedelta
    dt = datetime.strptime(month_str, "%Y-%m")
    prev = dt.replace(day=1) - timedelta(days=1)
    return prev.strftime("%Y-%m")
```

- **VALIDATE**: `source venv/bin/activate && python3 -c "from db import previous_month; assert previous_month('2026-02')=='2026-01'; assert previous_month('2026-01')=='2025-12'; print('OK')"`

### Task 4: CREATE `notifications.py` — Discord webhook alerts

**IMPLEMENT**: New file for sending Discord webhook notifications.

```python
"""Discord webhook notifications for budget alerts."""

import os
import logging
import aiohttp

log = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_BUDGET", "")


async def check_and_send_alerts(budgets_with_spending: list[dict]):
    """Check budgets and send Discord alerts for 80% and 100% thresholds.

    budgets_with_spending: output of get_budgets_with_spending()
    Each dict has: category_name, category_icon, spent, amount_max, percent
    """
    if not WEBHOOK_URL:
        log.debug("No DISCORD_WEBHOOK_BUDGET configured, skipping alerts")
        return

    alerts = []
    for b in budgets_with_spending:
        pct = b["percent"]
        if pct >= 100:
            alerts.append({"budget": b, "level": "critical"})
        elif pct >= 80:
            alerts.append({"budget": b, "level": "warning"})

    if not alerts:
        return

    for alert in alerts:
        await _send_alert(alert["budget"], alert["level"])


async def _send_alert(budget: dict, level: str):
    """Send a single budget alert to Discord."""
    icon = budget["category_icon"]
    name = budget["category_name"]
    spent = budget["spent"]
    limit = budget["amount_max"]
    pct = budget["percent"]

    if level == "critical":
        color = 0xF44336  # red
        title = "Budget depasse !"
        msg = f"Tu as depasse ta limite !"
    else:
        color = 0xFF9800  # orange
        title = "Attention budget"
        msg = f"Tu approches de ta limite !"

    embed = {
        "color": color,
        "title": f"{'🚨' if level == 'critical' else '⚠️'} {title}",
        "description": f"{icon} **{name}** : {spent:.2f}€ / {limit:.2f}€ ({pct:.0f}%)\n{msg}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(WEBHOOK_URL, json={"embeds": [embed]}) as resp:
                if resp.status == 204:
                    log.info(f"Alert sent: {name} at {pct:.0f}%")
                else:
                    text = await resp.text()
                    log.error(f"Discord webhook failed {resp.status}: {text}")
    except Exception as e:
        log.error(f"Discord webhook error: {e}")
```

- **GOTCHA**: `WEBHOOK_URL` is read from env at module load. If empty, alerts are silently skipped (log.debug).
- **GOTCHA**: Use `aiohttp.ClientSession()` (not requests) — we're in an async context.
- **GOTCHA**: Discord returns 204 No Content on success, not 200.
- **VALIDATE**: `source venv/bin/activate && python3 -c "from notifications import check_and_send_alerts; print('Import OK')"`

### Task 5: UPDATE `app.py` — Add budget routes

**IMPLEMENT**: Add the following handler functions and register routes.

**New imports** (add at top of app.py):

```python
import uuid
from db import (
    # ... existing imports ...
    get_budgets_with_spending,
    get_budget_by_id,
    get_month_comparison,
    get_setting,
    insert_budget,
    delete_budget,
    previous_month,
    set_setting,
    update_budget,
)
from notifications import check_and_send_alerts
```

**New handlers**:

```python
async def budgets_page(request):
    """GET /budgets — Envelopes management page."""
    months = get_months(db)
    month = request.query.get("month")
    if not month:
        month = months[0] if months else None

    budgets = get_budgets_with_spending(db, month) if month else []
    categories = get_categories(db)
    # Filter out categories that already have a budget
    budget_cat_ids = {b["category_id"] for b in budgets}
    available_categories = [c for c in categories if c["id"] not in budget_cat_ids]

    return aiohttp_jinja2.render_template("budgets.html", request, {
        "active": "budgets",
        "month": month,
        "months": months,
        "budgets": budgets,
        "categories": categories,
        "available_categories": available_categories,
    })


async def budgets_create(request):
    """POST /budgets — Create or update a budget envelope."""
    data = await request.post()
    category_id = int(data.get("category_id", 0))
    amount_max = float(data.get("amount_max", 0))
    budget_id = data.get("budget_id")  # If set, it's an update

    if category_id and amount_max > 0:
        if budget_id:
            update_budget(db, int(budget_id), amount_max)
        else:
            insert_budget(db, category_id, amount_max)

    # Redirect back to budgets page
    month = data.get("month", "")
    raise web.HTTPFound(f"/budgets?month={month}" if month else "/budgets")


async def budgets_delete_handler(request):
    """POST /api/budgets/{id}/delete — Delete a budget envelope."""
    budget_id = int(request.match_info["id"])
    delete_budget(db, budget_id)
    return web.json_response({"ok": True})
```

**Share page handler**:

```python
async def share_page(request):
    """GET /share/{token} — Public monthly summary for father."""
    token = request.match_info["token"]
    expected_token = get_setting(db, "share_token") or os.getenv("SHARE_TOKEN", "")

    if not expected_token or token != expected_token:
        raise web.HTTPNotFound(text="Lien invalide")

    months = get_months(db)
    month = request.query.get("month")
    if not month:
        month = months[0] if months else None

    if not month:
        return aiohttp_jinja2.render_template("share.html", request, {
            "month": None, "months": months,
        })

    summary = get_month_summary(db, month)
    solde_initial = get_solde_initial(db, month)

    return aiohttp_jinja2.render_template("share.html", request, {
        "month": month,
        "months": months,
        "summary": summary,
        "solde_initial": solde_initial,
    })
```

**Update `import_upload`** — Add alert check after successful import (after `insert_transactions`):

```python
# After insert_transactions(db, import_id, transactions) in import_upload():
# Check budget alerts
try:
    month = result.get("period_start", "")[:7] if result.get("period_start") else None
    if month:
        budgets_data = get_budgets_with_spending(db, month)
        await check_and_send_alerts(budgets_data)
except Exception as e:
    pass  # Don't fail import because of alert errors
```

**Update `dashboard_page`** — Add comparison data:

```python
# After getting top_expenses, add:
prev_month = previous_month(month)
comparison = get_month_comparison(db, month, prev_month) if prev_month in months else []
# Add "comparison": comparison to the template context dict
```

**Update `create_app()`** — Register new routes:

```python
app.router.add_get("/budgets", budgets_page)
app.router.add_post("/budgets", budgets_create)
app.router.add_post("/api/budgets/{id}/delete", budgets_delete_handler)
app.router.add_get("/share/{token}", share_page)
```

**Update startup** — Generate share token if not set:

```python
# In `if __name__ == "__main__":` block, after init_db():
if not get_setting(db, "share_token"):
    token = os.getenv("SHARE_TOKEN") or str(uuid.uuid4())
    set_setting(db, "share_token", token)
    print(f"Share URL: http://{HOST}:{PORT}/share/{token}")
else:
    print(f"Share URL: http://{HOST}:{PORT}/share/{get_setting(db, 'share_token')}")
```

- **IMPORTS**: `import uuid` (add at top)
- **GOTCHA**: `budgets_create` uses `request.post()` (form data), not `request.json()` — it's a regular HTML form submit, not a fetch API call.
- **GOTCHA**: `budgets_delete_handler` uses POST (not DELETE) because fetch from JS is simpler and HTML forms only support GET/POST.
- **GOTCHA**: Alert check in `import_upload` is wrapped in try/except — a webhook failure must not break the import flow.
- **VALIDATE**: `source venv/bin/activate && python3 -c "from app import create_app; print('App created OK')"`

### Task 6: UPDATE `templates/base.html` — Add nav link for Enveloppes

**IMPLEMENT**: Add "Enveloppes" link in the nav between "Transactions" and "Import":

Change the nav-links div (line 12-16) to:

```html
<div class="nav-links">
    <a href="/" class="nav-link {% if active == 'dashboard' %}active{% endif %}">Dashboard</a>
    <a href="/transactions" class="nav-link {% if active == 'transactions' %}active{% endif %}">Transactions</a>
    <a href="/budgets" class="nav-link {% if active == 'budgets' %}active{% endif %}">Enveloppes</a>
    <a href="/import" class="nav-link {% if active == 'import' %}active{% endif %}">Import</a>
</div>
```

- **VALIDATE**: `grep -c 'budgets' templates/base.html` (should be >= 1)

### Task 7: CREATE `templates/budgets.html` — Envelopes page

**IMPLEMENT**: Extends base.html. Contains:

1. **Month navigation** — Same pattern as dashboard.html (prev/next buttons, month title)
2. **Budget list** — Cards with progress bars for each active budget
3. **Create form** — Category dropdown (only categories without existing budget) + amount input + submit
4. **Edit/delete** — Each budget card has edit (inline form) and delete button

Template structure:

```html
{% extends "base.html" %}
{% block title %}Enveloppes — Budget Tracker{% endblock %}
{% block content %}

{% if not month %}
<div class="empty-state">
    <span class="empty-icon">&#128176;</span>
    <h2>Aucune donnee</h2>
    <p>Importez un releve pour gerer vos enveloppes.</p>
    <a href="/import" class="btn btn-primary">Importer un releve</a>
</div>
{% else %}

<!-- Month navigation (same as dashboard) -->
<div class="month-nav">
    <button class="btn btn-icon" id="prev-month">&larr;</button>
    <h1 class="month-title" id="current-month">{{ month }}</h1>
    <button class="btn btn-icon" id="next-month">&rarr;</button>
</div>

<!-- Budget list -->
<div class="budget-list">
    {% for b in budgets %}
    <div class="budget-card">
        <div class="budget-header">
            <span class="budget-category">{{ b.category_icon }} {{ b.category_name }}</span>
            <span class="budget-amounts">{{ "%.2f"|format(b.spent) }}&euro; / {{ "%.2f"|format(b.amount_max) }}&euro;</span>
        </div>
        <div class="progress-bar">
            <div class="progress-fill {% if b.percent >= 100 %}critical{% elif b.percent >= 80 %}warning{% elif b.percent >= 60 %}caution{% endif %}"
                 style="width: {{ [b.percent, 100] | min }}%">
            </div>
        </div>
        <div class="budget-footer">
            <span class="budget-percent {% if b.percent >= 100 %}critical{% elif b.percent >= 80 %}warning{% endif %}">
                {{ "%.0f"|format(b.percent) }}%
            </span>
            <div class="budget-actions">
                <button class="btn-small btn-edit" onclick="editBudget({{ b.id }}, {{ b.amount_max }})">Modifier</button>
                <button class="btn-small btn-delete" onclick="deleteBudget({{ b.id }})">Supprimer</button>
            </div>
        </div>
    </div>
    {% endfor %}
</div>

<!-- Edit modal (hidden) -->
<div class="modal-overlay" id="edit-modal" style="display:none">
    <div class="modal">
        <h3>Modifier l'enveloppe</h3>
        <form method="post" action="/budgets">
            <input type="hidden" name="budget_id" id="edit-budget-id">
            <input type="hidden" name="category_id" value="0" id="edit-category-id">
            <input type="hidden" name="month" value="{{ month }}">
            <div class="form-group">
                <label>Montant max (&euro;/mois)</label>
                <input type="number" name="amount_max" id="edit-amount" step="0.01" min="1" class="filter-input" required>
            </div>
            <div class="modal-actions">
                <button type="button" class="btn btn-secondary" onclick="document.getElementById('edit-modal').style.display='none'">Annuler</button>
                <button type="submit" class="btn btn-primary">Enregistrer</button>
            </div>
        </form>
    </div>
</div>

<!-- Create new envelope -->
{% if available_categories %}
<div class="card">
    <h2>Creer une enveloppe</h2>
    <form method="post" action="/budgets" class="budget-create-form">
        <input type="hidden" name="month" value="{{ month }}">
        <div class="form-row">
            <select name="category_id" class="filter-select" required>
                <option value="">Choisir une categorie</option>
                {% for cat in available_categories %}
                <option value="{{ cat.id }}">{{ cat.icon }} {{ cat.name }}</option>
                {% endfor %}
            </select>
            <input type="number" name="amount_max" placeholder="Budget max (EUR)" step="0.01" min="1" class="filter-input" required>
            <button type="submit" class="btn btn-primary">Creer</button>
        </div>
    </form>
</div>
{% endif %}

{% endif %}
{% endblock %}

{% block scripts %}
{% if month %}
<script src="/static/js/app.js"></script>
<script>
    const MONTHS = {{ months | tojson }};
    const CURRENT_MONTH = {{ month | tojson }};

    document.addEventListener('DOMContentLoaded', function() {
        initMonthNav(MONTHS, CURRENT_MONTH);
    });

    function editBudget(id, currentAmount) {
        document.getElementById('edit-budget-id').value = id;
        document.getElementById('edit-amount').value = currentAmount;
        document.getElementById('edit-modal').style.display = 'flex';
    }

    function deleteBudget(id) {
        if (!confirm('Supprimer cette enveloppe ?')) return;
        fetch('/api/budgets/' + id + '/delete', { method: 'POST' })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.ok) window.location.reload();
            });
    }
</script>
{% endif %}
{% endblock %}
```

- **GOTCHA**: Progress bar width is capped at 100% via `{{ [b.percent, 100] | min }}` but the percentage label can show > 100%.
- **GOTCHA**: The `edit-category-id` hidden field isn't strictly needed for updates (the budget_id identifies the record), but the POST handler uses `category_id` for inserts vs updates branching.
- **VALIDATE**: `test -f templates/budgets.html && echo 'OK'`

### Task 8: CREATE `templates/share.html` — Father's share page

**IMPLEMENT**: Standalone-looking page (extends base.html but with minimal nav). Shows monthly summary: total expenses, category donut, balance. NO transaction details (privacy).

```html
{% extends "base.html" %}
{% block title %}Resume mensuel — Budget Tracker{% endblock %}
{% block content %}

{% if not month %}
<div class="empty-state">
    <span class="empty-icon">&#128202;</span>
    <h2>Aucune donnee disponible</h2>
    <p>Aucun releve n'a encore ete importe.</p>
</div>
{% else %}

<div class="share-header">
    <h1>Resume mensuel</h1>
    <p class="share-subtitle">{{ month }}</p>
</div>

<!-- Month selector (simple, no prev/next — just a dropdown) -->
{% if months | length > 1 %}
<div class="share-month-select">
    <select onchange="window.location.search='?month='+this.value" class="filter-select">
        {% for m in months %}
        <option value="{{ m }}" {{ 'selected' if m == month else '' }}>{{ m }}</option>
        {% endfor %}
    </select>
</div>
{% endif %}

<!-- Stats -->
<div class="stats-grid">
    <div class="stat-card">
        <span class="stat-label">Depenses</span>
        <span class="stat-value expense">{{ "%.2f"|format(summary.total_depenses) }} &euro;</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Revenus</span>
        <span class="stat-value income">{{ "%.2f"|format(summary.total_revenus) }} &euro;</span>
    </div>
    {% if solde_initial is not none %}
    <div class="stat-card">
        <span class="stat-label">Solde initial</span>
        <span class="stat-value">{{ "%.2f"|format(solde_initial) }} &euro;</span>
    </div>
    {% endif %}
    <div class="stat-card">
        <span class="stat-label">Transactions</span>
        <span class="stat-value">{{ summary.tx_count }}</span>
    </div>
</div>

<!-- Category donut -->
<div class="card">
    <h2>Depenses par categorie</h2>
    <div class="chart-container">
        <canvas id="share-donut"></canvas>
    </div>
</div>

{% endif %}
{% endblock %}

{% block scripts %}
{% if month %}
<script src="/static/js/charts.js"></script>
<script>
    const CATEGORY_DATA = {{ summary.categories | tojson }};
    document.addEventListener('DOMContentLoaded', function() {
        initCategoryDonut('share-donut', CATEGORY_DATA);
    });
</script>
{% endif %}
{% endblock %}
```

- **GOTCHA**: No transaction list, no transaction amounts, no libelles — only aggregate data (privacy for Arnaud).
- **GOTCHA**: The nav from base.html will show on the share page. This is acceptable — the father can see the nav but other pages require no auth anyway. If strict isolation is needed, create a separate `share_base.html` without nav. For MVP, reusing base.html is simpler and the PRD doesn't prohibit it.
- **VALIDATE**: `test -f templates/share.html && echo 'OK'`

### Task 9: UPDATE `templates/dashboard.html` — Add comparison section

**IMPLEMENT**: Add a comparison section between the charts and top expenses. Only show if `comparison` data is available.

Add this block after the `charts-grid` div and before the top expenses section:

```html
<!-- Month comparison -->
{% if comparison %}
<div class="card">
    <h2>Comparaison avec le mois precedent</h2>
    <div class="comparison-grid">
        {% for c in comparison %}
        <div class="comparison-row">
            <span class="comparison-category">{{ c.icon }} {{ c.name }}</span>
            <span class="comparison-current">{{ "%.2f"|format(c.current) }}&euro;</span>
            <span class="comparison-delta {% if c.delta > 0 %}expense{% elif c.delta < 0 %}income{% endif %}">
                {% if c.delta > 0 %}+{% endif %}{{ "%.2f"|format(c.delta) }}&euro;
                {% if c.delta_pct is not none %}
                ({% if c.delta_pct > 0 %}+{% endif %}{{ c.delta_pct }}%)
                {% endif %}
            </span>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}
```

Also update the `<script>` block to pass comparison data (not needed for JS, purely server-rendered).

Add `comparison` to the template context in `dashboard_page()` handler (see Task 5).

- **VALIDATE**: `grep -c 'comparison' templates/dashboard.html` (should be >= 1)

### Task 10: UPDATE `static/css/style.css` — Add progress bar + budget + share styles

**IMPLEMENT**: Add these CSS rules at the end of style.css (before the responsive media queries):

```css
/* ===== Phase 3 — Budgets + Share ===== */

/* Budget list */
.budget-list { display: flex; flex-direction: column; gap: 1rem; margin-bottom: 2rem; }
.budget-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
}
.budget-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}
.budget-category { font-weight: 600; }
.budget-amounts { color: var(--text-muted); font-size: 0.9rem; }

/* Progress bar */
.progress-bar {
    height: 12px;
    background: var(--bg-input);
    border-radius: 6px;
    overflow: hidden;
    margin-bottom: 0.5rem;
}
.progress-fill {
    height: 100%;
    background: var(--success);
    border-radius: 6px;
    transition: width 0.3s ease;
}
.progress-fill.caution { background: #FFC107; }
.progress-fill.warning { background: var(--warning, #FF9800); }
.progress-fill.critical { background: var(--error); }

.budget-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.budget-percent { font-weight: 700; font-size: 0.9rem; }
.budget-percent.warning { color: var(--warning, #FF9800); }
.budget-percent.critical { color: var(--error); }
.budget-actions { display: flex; gap: 0.5rem; }

.btn-small {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-muted);
    padding: 0.25rem 0.75rem;
    font-size: 0.8rem;
    cursor: pointer;
}
.btn-small:hover { border-color: var(--accent); color: var(--accent); }
.btn-small.btn-delete:hover { border-color: var(--error); color: var(--error); }

/* Budget create form */
.budget-create-form .form-row {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
}
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.25rem; }

/* Comparison grid */
.comparison-grid { display: flex; flex-direction: column; gap: 0.5rem; }
.comparison-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
}
.comparison-row:last-child { border-bottom: none; }
.comparison-category { flex: 1; }
.comparison-current { color: var(--text-muted); min-width: 80px; text-align: right; }
.comparison-delta { font-weight: 600; min-width: 120px; text-align: right; }

/* Share page */
.share-header { text-align: center; margin-bottom: 2rem; }
.share-subtitle { color: var(--text-muted); font-size: 1.2rem; }
.share-month-select { text-align: center; margin-bottom: 2rem; }
```

Also add `--warning: #FF9800;` to the `:root` variables if not present (it's not currently in the CSS vars, only used as color for Bar/Tabac category).

- **VALIDATE**: `grep -c 'progress-bar' static/css/style.css` (should be >= 1)

### Task 11: UPDATE `static/css/style.css` — Add --warning var to :root

**IMPLEMENT**: Add `--warning: #FF9800;` to the `:root` block (after `--error`):

```css
:root {
    /* ... existing vars ... */
    --error: #f44336;
    --warning: #FF9800;
    /* ... */
}
```

- **VALIDATE**: `grep 'warning' static/css/style.css | head -3`

### Task 12: UPDATE responsive media queries

**IMPLEMENT**: Add budget-specific responsive rules in the existing `@media (max-width: 600px)` block:

```css
@media (max-width: 600px) {
    /* ... existing rules ... */
    .budget-create-form .form-row { flex-direction: column; }
    .budget-header { flex-direction: column; align-items: flex-start; gap: 0.25rem; }
    .comparison-row { flex-wrap: wrap; }
    .comparison-delta { min-width: auto; }
}
```

- **VALIDATE**: `tail -20 static/css/style.css`

### Task 13: CREATE `tests/test_budgets.py` — Unit tests

**IMPLEMENT**: Tests for budget CRUD, month comparison, settings, and notification formatting.

```python
"""Tests for Phase 3 — Budgets, settings, comparison, notifications."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import (
    init_db,
    insert_budget,
    get_budgets_with_spending,
    update_budget,
    delete_budget,
    get_budget_by_id,
    get_setting,
    set_setting,
    insert_import,
    insert_transactions,
    get_month_comparison,
    previous_month,
)


def _setup_db():
    """Create in-memory DB with test data."""
    db = init_db(":memory:")
    # Insert a fake import
    import_id = insert_import(db, "test.pdf", "abc123", "2026-01-31", "2026-02-27", 2, 100.0, 90.0)
    # Insert test transactions (category_id 1 = Courses, 2 = Bar/Tabac)
    insert_transactions(db, import_id, [
        {"date_operation": "2026-02-05", "date_valeur": "2026-02-05", "libelle": "INTERMARCHE", "montant": -50.0, "category_id": 1},
        {"date_operation": "2026-02-10", "date_valeur": "2026-02-10", "libelle": "LE BALTO", "montant": -30.0, "category_id": 2},
    ])
    return db


def test_budget_crud():
    db = _setup_db()
    # Create
    bid = insert_budget(db, 1, 100.0)
    assert bid is not None
    budget = get_budget_by_id(db, bid)
    assert budget["amount_max"] == 100.0
    assert budget["category_name"] == "Courses"

    # Update
    update_budget(db, bid, 150.0)
    budget = get_budget_by_id(db, bid)
    assert budget["amount_max"] == 150.0

    # Delete
    delete_budget(db, bid)
    assert get_budget_by_id(db, bid) is None


def test_budgets_with_spending():
    db = _setup_db()
    insert_budget(db, 1, 100.0)  # Courses, limit 100
    insert_budget(db, 2, 25.0)   # Bar/Tabac, limit 25

    budgets = get_budgets_with_spending(db, "2026-02")
    assert len(budgets) == 2

    courses = next(b for b in budgets if b["category_name"] == "Courses")
    assert courses["spent"] == 50.0
    assert courses["percent"] == 50.0

    bar = next(b for b in budgets if b["category_name"] == "Bar / Tabac")
    assert bar["spent"] == 30.0
    assert bar["percent"] == 120.0  # Over budget!


def test_settings():
    db = _setup_db()
    assert get_setting(db, "share_token") is None
    set_setting(db, "share_token", "test-token-123")
    assert get_setting(db, "share_token") == "test-token-123"
    # Update
    set_setting(db, "share_token", "new-token")
    assert get_setting(db, "share_token") == "new-token"


def test_previous_month():
    assert previous_month("2026-02") == "2026-01"
    assert previous_month("2026-01") == "2025-12"
    assert previous_month("2026-12") == "2026-11"


def test_month_comparison():
    db = _setup_db()
    # Add January data
    import_id2 = insert_import(db, "test2.pdf", "def456", "2025-12-31", "2026-01-31", 1, 200.0, 180.0)
    insert_transactions(db, import_id2, [
        {"date_operation": "2026-01-15", "date_valeur": "2026-01-15", "libelle": "INTERMARCHE", "montant": -80.0, "category_id": 1},
    ])

    comparison = get_month_comparison(db, "2026-02", "2026-01")
    courses = next((c for c in comparison if c["name"] == "Courses"), None)
    assert courses is not None
    assert courses["current"] == 50.0
    assert courses["previous"] == 80.0
    assert courses["delta"] == -30.0
    assert courses["delta_pct"] == -37.5


if __name__ == "__main__":
    test_budget_crud()
    test_budgets_with_spending()
    test_settings()
    test_previous_month()
    test_month_comparison()
    print("All Phase 3 tests passed!")
```

- **GOTCHA**: `init_db(":memory:")` creates an in-memory SQLite DB — perfect for tests, no cleanup needed. However, the current `init_db` creates directories with `os.makedirs(data_dir)` which will fail for ":memory:". Need to handle this: either pass a temp dir or guard the `os.makedirs` call.
- **GOTCHA**: Fix `init_db` to handle in-memory DB: add `if data_dir != ":memory:": os.makedirs(data_dir, exist_ok=True)` before the `os.path.join`. Or better: detect `:memory:` and skip dir creation.
- **VALIDATE**: `source venv/bin/activate && python3 tests/test_budgets.py`

### Task 14: UPDATE `db.py` — Handle `:memory:` in init_db

**IMPLEMENT**: At the beginning of `init_db()`, handle in-memory DB for tests:

```python
def init_db(data_dir: str) -> sqlite3.Connection:
    """Create data dir and initialize SQLite with full schema."""
    if data_dir == ":memory:":
        db = sqlite3.connect(":memory:")
    else:
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "budget.db")
        db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    # ... rest unchanged ...
```

- **VALIDATE**: `source venv/bin/activate && python3 -c "from db import init_db; db=init_db(':memory:'); print('OK')"`

### Task 15: Run all tests

- **VALIDATE**: `source venv/bin/activate && python3 tests/test_parser.py && python3 tests/test_budgets.py`

---

## TESTING STRATEGY

### Unit Tests (tests/test_budgets.py)

- `test_budget_crud` — Create, read, update, delete budget
- `test_budgets_with_spending` — Verify spent amounts and percentages computed from transactions
- `test_settings` — Set/get/update settings
- `test_previous_month` — Month arithmetic including year boundary
- `test_month_comparison` — Delta computation between two months

### Integration Tests (manual)

- Start server, create a budget, verify progress bar renders
- Import a PDF, check that alerts would trigger (check logs if no webhook configured)
- Open share page with valid token, verify summary displays
- Open share page with invalid token, verify 404

### Edge Cases

- Budget for a category with zero spending (0% — green bar)
- Budget with spending > 200% (bar capped at 100% width, label shows real %)
- Share page for a month with no data (empty state)
- Month comparison when previous month has no data (comparison section hidden)
- Discord webhook URL not configured (silent skip, no crash)
- Discord webhook URL returns error (logged, import not affected)

---

## VALIDATION COMMANDS

### Level 1: Syntax

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
source venv/bin/activate
python3 -m py_compile app.py
python3 -m py_compile db.py
python3 -m py_compile notifications.py
python3 -m py_compile categorizer.py
```

### Level 2: Unit Tests

```bash
python3 tests/test_parser.py
python3 tests/test_budgets.py
```

### Level 3: Integration (server)

```bash
python3 app.py &
sleep 2

# Budgets page
curl -s http://localhost:8080/budgets | grep "Enveloppes"

# Create budget (Courses = 200 EUR)
curl -s -X POST http://localhost:8080/budgets -d "category_id=1&amount_max=200&month=2026-02" -L | grep "progress"

# Share page (get token from logs or DB)
# curl -s http://localhost:8080/share/<token> | grep "Resume mensuel"

# Invalid share token
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/share/invalid-token
# Should return 404

# Delete budget via API
# curl -s -X POST http://localhost:8080/api/budgets/1/delete

kill %1
```

### Level 4: Manual Validation (browser)

1. Open `/budgets` — see empty state or budget list
2. Create a budget for "Courses" at 200 EUR — see green progress bar
3. Create a budget for "Bar / Tabac" at 20 EUR — see red progress bar (over 100%)
4. Edit the Bar/Tabac budget to 80 EUR — see progress update
5. Delete a budget — confirm and verify removal
6. Open `/share/<token>` — see monthly summary with donut, no tx details
7. Open `/share/wrong-token` — see 404
8. Check dashboard for comparison section (if 2+ months of data)

---

## ACCEPTANCE CRITERIA

- [ ] Budget envelopes: create, read, update, delete via `/budgets` page
- [ ] Progress bars: green < 60%, yellow 60-80%, orange 80-100%, red > 100%
- [ ] Only categories without existing budget shown in create form
- [ ] Discord alerts sent on 80% and 100% thresholds after import (if webhook configured)
- [ ] Alert failure doesn't break import flow
- [ ] Share page accessible at `/share/<token>` with valid token
- [ ] Share page shows: month, total expenses, total income, solde, category donut
- [ ] Share page does NOT show individual transaction details
- [ ] Invalid token returns 404
- [ ] Share token generated once on first startup, persisted in settings table
- [ ] Month-to-month comparison shown on dashboard (deltas per category)
- [ ] All existing tests still pass (no regressions)
- [ ] New tests pass (test_budgets.py)
- [ ] Dark theme consistent across all new pages
- [ ] Responsive layout works on mobile (600px breakpoint)

---

## COMPLETION CHECKLIST

- [ ] db.py: settings CRUD (get_setting, set_setting)
- [ ] db.py: budget CRUD (insert, update, delete, get_by_id, get_with_spending)
- [ ] db.py: month comparison (get_month_comparison, previous_month)
- [ ] db.py: init_db handles `:memory:` for tests
- [ ] notifications.py: Discord webhook sender (check_and_send_alerts)
- [ ] app.py: budget routes (GET /budgets, POST /budgets, POST /api/budgets/{id}/delete)
- [ ] app.py: share route (GET /share/{token})
- [ ] app.py: alert check after import
- [ ] app.py: comparison data passed to dashboard
- [ ] app.py: share token generation on startup
- [ ] templates/base.html: nav link for Enveloppes
- [ ] templates/budgets.html: full page with progress bars, create/edit/delete
- [ ] templates/share.html: public summary page
- [ ] templates/dashboard.html: comparison section
- [ ] static/css/style.css: progress bar + budget + share + comparison styles
- [ ] tests/test_budgets.py: all tests pass
- [ ] tests/test_parser.py: no regressions
- [ ] Commit + push

---

## NOTES

- **No new Python dependencies needed** — aiohttp (for webhook), uuid, datetime are all stdlib or already installed.
- **Discord webhook is fire-and-forget** — wrapped in try/except, logged but never blocks the import flow. If `DISCORD_WEBHOOK_BUDGET` is empty, nothing happens.
- **Share token persistence** — Stored in `settings` table (SQLite), not just .env. Generated via `uuid.uuid4()` on first startup. Can be overridden via `SHARE_TOKEN` env var.
- **Month comparison** — Only shown when previous month has data in DB. Uses existing `get_month_summary()` to avoid duplicating query logic.
- **Budget "reset"** — Envelopes are permanent (no monthly reset needed). The `get_budgets_with_spending()` query filters transactions by the selected month, so spending resets naturally each month.
- **No authentication** — Consistent with Phases 1-2. The share page uses a token URL (security through obscurity), acceptable for this use case per PRD.
- **Edit budget** — Uses a modal with a form POST (same as create), with a hidden `budget_id` field to differentiate create from update.
- **Delete budget** — Uses fetch POST to `/api/budgets/{id}/delete` (not DELETE method) for simplicity with JS fetch. Returns JSON `{"ok": true}`, then JS reloads page.
