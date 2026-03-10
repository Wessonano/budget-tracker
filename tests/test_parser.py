"""Tests du parser BoursoBank sur le sample réel."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import convert_date, parse_amount, parse_boursobank

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "sample-boursobank.pdf")


def test_parse_amount():
    assert parse_amount("11,50") == 11.50
    assert parse_amount("1 234,56") == 1234.56
    assert parse_amount("100,00") == 100.00
    assert parse_amount("404,52") == 404.52


def test_convert_date():
    assert convert_date("02/02/2026") == "2026-02-02"
    assert convert_date("31/01/2026") == "2026-01-31"


def test_parse_full_pdf():
    """Test sur le vrai relevé BoursoBank."""
    result = parse_boursobank(SAMPLE_PDF)

    assert result["ok"] is True
    assert result["count"] >= 25
    assert result["period_start"] == "2026-01-31"
    assert result["period_end"] == "2026-02-27"
    assert result["solde_initial"] == 111.19
    assert result["solde_final"] == 107.52

    txs = result["transactions"]

    # Balance check: solde_initial + sum(montants) == solde_final
    balance = result["solde_initial"] + sum(t["montant"] for t in txs)
    assert abs(balance - result["solde_final"]) < 0.01, f"Balance mismatch: {balance}"

    # VIR INST crédit 100€
    vir_credits = [
        t
        for t in txs
        if "VIR INST M LARRIEU ARNAUD" in t["libelle"] and t["montant"] > 0
    ]
    assert len(vir_credits) >= 3

    # CARTE AGENALINE débit 11,50€
    agenaline = [t for t in txs if "AGENALINE" in t["libelle"]]
    assert len(agenaline) == 1
    assert agenaline[0]["montant"] == -11.50

    # AVOIR AMAZON crédit 53,35€
    avoir = [
        t
        for t in txs
        if "AVOIR" in t["libelle"] and "AMAZON" in t["libelle"] and t["montant"] > 0
    ]
    assert len(avoir) >= 1

    # VIR Erick débit 31€
    erick_debit = [
        t for t in txs if "LARRIEU ERICK" in t["libelle"] and t["montant"] < 0
    ]
    assert len(erick_debit) >= 1

    # CLAUDE.AI débit 216€
    claude = [t for t in txs if "CLAUDE.AI" in t["libelle"]]
    assert len(claude) == 1
    assert claude[0]["montant"] == -216.00

    # PAYPAL débit 404,52€
    paypal = [t for t in txs if "PAYPAL" in t["libelle"]]
    assert len(paypal) == 1
    assert paypal[0]["montant"] == -404.52


def test_transactions_have_dates():
    """Toutes les transactions ont des dates valides."""
    result = parse_boursobank(SAMPLE_PDF)
    for tx in result["transactions"]:
        assert tx["date_operation"] is not None
        assert len(tx["date_operation"]) == 10
        assert tx["date_operation"].startswith("2026-")


def test_multiline_transactions():
    """Les virements multi-lignes ont le nom dans le libellé."""
    result = parse_boursobank(SAMPLE_PDF)
    txs = result["transactions"]

    erick_txs = [t for t in txs if "ERICK" in t["libelle"].upper()]
    assert len(erick_txs) >= 1


if __name__ == "__main__":
    test_parse_amount()
    test_convert_date()
    test_parse_full_pdf()
    test_transactions_have_dates()
    test_multiline_transactions()
    print("All tests passed!")
