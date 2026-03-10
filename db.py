"""Database layer — SQLite init + CRUD."""

import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    sha256 TEXT UNIQUE NOT NULL,
    period_start TEXT,
    period_end TEXT,
    transaction_count INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    icon TEXT NOT NULL,
    color TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
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
"""

DEFAULT_CATEGORIES = [
    ("Courses", "\U0001f6d2", "#4CAF50", 1),
    ("Bar / Tabac", "\u2615", "#FF9800", 2),
    ("Abonnements tech", "\U0001f916", "#2196F3", 3),
    ("T\u00e9l\u00e9phone", "\U0001f4f1", "#9C27B0", 4),
    ("Internet", "\U0001f4e1", "#00BCD4", 5),
    ("Shopping", "\U0001f4e6", "#E91E63", 6),
    ("Famille", "\U0001f468\u200d\U0001f469\u200d\U0001f467", "#FF5722", 7),
    ("Transfert interne", "\U0001f504", "#607D8B", 8),
    ("Remboursement", "\u21a9\ufe0f", "#8BC34A", 9),
    ("Divers", "\U0001f4cc", "#9E9E9E", 10),
]

DEFAULT_PATTERNS = [
    ("Courses", "INTERMARCHE", 0),
    ("Courses", "AGENALINE", 0),
    ("Courses", "LECLERC", 0),
    ("Courses", "CARREFOUR", 0),
    ("Courses", "LIDL", 0),
    ("Courses", "ALDI", 0),
    ("Bar / Tabac", "LE BALTO", 0),
    ("Bar / Tabac", "TABAC", 0),
    ("Bar / Tabac", "MAISON DU PERO", 0),
    ("Bar / Tabac", "CAFE", 0),
    ("Abonnements tech", r"CLAUDE\.AI", 0),
    ("Abonnements tech", "PROTON", 0),
    ("Abonnements tech", r"GOOGLE.*CLOUD", 0),
    ("Abonnements tech", "Google Play", 0),
    ("Abonnements tech", "GANDI", 0),
    ("T\u00e9l\u00e9phone", "FREE MOBILE", 0),
    ("T\u00e9l\u00e9phone", "SFR", 0),
    ("T\u00e9l\u00e9phone", "ORANGE", 0),
    ("T\u00e9l\u00e9phone", "BOUYGUES", 0),
    ("Internet", r"FREE\b(?!.*MOBILE)", 0),
    ("Shopping", "AMAZON", 0),
    ("Shopping", "PAYPAL", 0),
    ("Famille", "LARRIEU ERICK", 0),
    ("Famille", "ELISA LARRIEU", 0),
    ("Famille", "CASTAING MARTINE", 0),
    ("Transfert interne", "VIR INST M LARRIEU ARNAUD", 0),
    ("Remboursement", "AVOIR", 0),
]


def init_db(data_dir: str) -> sqlite3.Connection:
    """Create data dir and initialize SQLite with full schema."""
    if data_dir == ":memory:":
        db = sqlite3.connect(":memory:")
    else:
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "budget.db")
        db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    # Migration: add solde columns to imports (Phase 2)
    try:
        db.execute("ALTER TABLE imports ADD COLUMN solde_initial REAL")
        db.execute("ALTER TABLE imports ADD COLUMN solde_final REAL")
        db.commit()
    except sqlite3.OperationalError:
        pass  # Columns already exist
    seed_categories(db)
    seed_patterns(db)
    return db


def seed_categories(db: sqlite3.Connection):
    """Insert default categories if table is empty."""
    count = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if count > 0:
        return
    db.executemany(
        "INSERT INTO categories (name, icon, color, sort_order) VALUES (?, ?, ?, ?)",
        DEFAULT_CATEGORIES,
    )
    db.commit()


def seed_patterns(db: sqlite3.Connection):
    """Insert default patterns if table is empty."""
    count = db.execute("SELECT COUNT(*) FROM category_patterns").fetchone()[0]
    if count > 0:
        return
    for cat_name, pattern, priority in DEFAULT_PATTERNS:
        cat = db.execute(
            "SELECT id FROM categories WHERE name = ?", (cat_name,)
        ).fetchone()
        if cat:
            db.execute(
                "INSERT INTO category_patterns (category_id, pattern, priority) VALUES (?, ?, ?)",
                (cat["id"], pattern, priority),
            )
    db.commit()


# --- CRUD ---


def get_import_by_hash(db: sqlite3.Connection, sha256: str) -> dict | None:
    row = db.execute("SELECT * FROM imports WHERE sha256 = ?", (sha256,)).fetchone()
    return dict(row) if row else None


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


def insert_transactions(
    db: sqlite3.Connection, import_id: int, transactions: list[dict]
) -> int:
    for tx in transactions:
        db.execute(
            "INSERT INTO transactions (import_id, date_operation, date_valeur, libelle, montant, category_id) VALUES (?, ?, ?, ?, ?, ?)",
            (
                import_id,
                tx["date_operation"],
                tx.get("date_valeur"),
                tx["libelle"],
                tx["montant"],
                tx.get("category_id"),
            ),
        )
    db.commit()
    return len(transactions)


def get_categories(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM categories ORDER BY sort_order"
    ).fetchall()
    return [dict(r) for r in rows]


def get_patterns(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT cp.*, c.name as category_name FROM category_patterns cp JOIN categories c ON cp.category_id = c.id ORDER BY cp.priority DESC, cp.id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_transactions(db: sqlite3.Connection, month: str) -> list[dict]:
    rows = db.execute(
        """SELECT t.*, c.name as category_name, c.icon as category_icon, c.color as category_color
           FROM transactions t
           LEFT JOIN categories c ON t.category_id = c.id
           WHERE strftime('%Y-%m', t.date_operation) = ?
           ORDER BY t.date_operation DESC""",
        (month,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_months(db: sqlite3.Connection) -> list[str]:
    rows = db.execute(
        "SELECT DISTINCT strftime('%Y-%m', date_operation) as month FROM transactions ORDER BY month DESC"
    ).fetchall()
    return [r["month"] for r in rows]


def get_import_history(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM imports ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# --- Phase 2 functions ---


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

    stats_row = db.execute(
        """SELECT
              COALESCE(SUM(CASE WHEN montant < 0 THEN ABS(montant) ELSE 0 END), 0) as total_depenses,
              COALESCE(SUM(CASE WHEN montant > 0 THEN montant ELSE 0 END), 0) as total_revenus,
              COUNT(*) as tx_count
           FROM transactions
           WHERE strftime('%Y-%m', date_operation) = ?""",
        (month,),
    ).fetchone()

    return {
        "categories": categories,
        "total_depenses": stats_row["total_depenses"] if stats_row else 0,
        "total_revenus": stats_row["total_revenus"] if stats_row else 0,
        "tx_count": stats_row["tx_count"] if stats_row else 0,
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
        balance += row["day_total"]
        balances.append({"date": row["date_operation"], "balance": round(balance, 2)})
    return balances


def get_solde_initial(db: sqlite3.Connection, month: str) -> float | None:
    """Get solde_initial from import matching this month."""
    row = db.execute(
        """SELECT i.solde_initial FROM imports i
           JOIN transactions t ON t.import_id = i.id
           WHERE strftime('%Y-%m', t.date_operation) = ?
           LIMIT 1""",
        (month,),
    ).fetchone()
    return row["solde_initial"] if row and row["solde_initial"] is not None else None


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


# --- Phase 3 functions ---


def get_setting(db: sqlite3.Connection, key: str) -> str | None:
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(db: sqlite3.Connection, key: str, value: str):
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )
    db.commit()


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


def previous_month(month_str: str) -> str:
    """'2026-02' -> '2026-01', '2026-01' -> '2025-12'"""
    from datetime import datetime, timedelta
    dt = datetime.strptime(month_str, "%Y-%m")
    prev = dt.replace(day=1) - timedelta(days=1)
    return prev.strftime("%Y-%m")


def get_month_comparison(db: sqlite3.Connection, current_month: str, previous_month_str: str) -> list[dict]:
    """Compare spending between two months. Returns deltas per category."""
    current = get_month_summary(db, current_month)
    previous = get_month_summary(db, previous_month_str)

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
