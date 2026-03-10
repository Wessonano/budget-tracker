"""Auto-categorization — pattern matching on transaction labels."""

import re
import sqlite3


def categorize_transaction(
    libelle: str, montant: float, patterns: list[dict]
) -> int | None:
    """Match a label against patterns, return category_id or None (=Divers).

    patterns: list of {'pattern': str, 'category_id': int, 'priority': int, 'category_name': str}
    sorted by priority DESC.
    """
    libelle_upper = libelle.upper()
    for p in patterns:
        try:
            if re.search(p["pattern"], libelle_upper, re.IGNORECASE):
                # "Transfert interne" only matches credits (montant > 0)
                if p["category_name"] == "Transfert interne" and montant < 0:
                    continue
                return p["category_id"]
        except re.error:
            continue  # Skip malformed patterns
    return None


def categorize_transactions(
    transactions: list[dict], db: sqlite3.Connection
) -> list[dict]:
    """Categorize all transactions. Returns transactions with category_id added."""
    from db import get_categories, get_patterns

    patterns = get_patterns(db)
    categories = get_categories(db)

    # Find "Divers" fallback id
    divers_id = next((c["id"] for c in categories if c["name"] == "Divers"), None)

    for tx in transactions:
        cat_id = categorize_transaction(tx["libelle"], tx["montant"], patterns)
        tx["category_id"] = cat_id if cat_id is not None else divers_id

    return transactions
