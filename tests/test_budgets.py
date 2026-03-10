"""Tests for Phase 3 — Budgets, settings, comparison, notifications."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import (
    delete_budget,
    get_budget_by_id,
    get_budgets_with_spending,
    get_month_comparison,
    get_setting,
    init_db,
    insert_budget,
    insert_import,
    insert_transactions,
    previous_month,
    set_setting,
    update_budget,
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
