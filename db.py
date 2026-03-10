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
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "budget.db")
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
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
) -> int:
    cur = db.execute(
        "INSERT INTO imports (filename, sha256, period_start, period_end, transaction_count) VALUES (?, ?, ?, ?, ?)",
        (filename, sha256, period_start, period_end, count),
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
