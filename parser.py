"""BoursoBank PDF parser — pdftotext -layout + regex extraction."""

import re
import subprocess


# Lines to skip — only applied to non-transaction lines (no date prefix)
SKIP_PATTERNS = [
    "MOUVEMENTS EN EUR",
    "opération",
    "réception",
    "approbation",
    "Boursorama",
    "Traversière",
    "Clientèle",
    "médiateur",
    "B.I.C.",
    "Mod.",
    "N° de RIB",
    "Banque Guichet",
    "Extrait de votre",
    "Protégé par",
    "BOURSOBANK",
    "RUE DE",
    "APPARTEMENT",
    "frais bancaires",
    "I.B.A.N.",
    "Montant DA",
    "MontantDA",
    "Libellé",
    "Valeur",
]

# Column position threshold: amounts starting before this = debit, after = credit
# Measured from real PDF: debits at pos 135-138, credits at pos 157-159
CREDIT_COLUMN_THRESHOLD = 150


def convert_date(date_fr: str) -> str:
    """DD/MM/YYYY -> YYYY-MM-DD"""
    parts = date_fr.split("/")
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


def parse_amount(raw: str) -> float:
    """'1 234,56' -> 1234.56"""
    return float(raw.replace("\u00a0", "").replace(" ", "").replace(",", "."))


def parse_boursobank(pdf_path: str) -> dict:
    """Parse a BoursoBank PDF statement.

    Returns {'ok': True, 'transactions': [...], 'period_start', 'period_end',
             'solde_initial', 'solde_final', 'count'}
    or {'ok': False, 'error': str}
    """
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"ok": False, "error": f"pdftotext failed: {result.stderr}"}

    lines = result.stdout.split("\n")

    transactions = []
    current_tx = None
    solde_initial = None
    solde_final = None
    period_start = None
    period_end = None

    for full_line in lines:
        stripped = full_line.strip()
        if not stripped:
            continue

        # --- Special lines (checked first, on ALL lines) ---

        # Period extraction
        period_match = re.search(
            r"du (\d{2}/\d{2}/\d{4}) au (\d{2}/\d{2}/\d{4})", full_line
        )
        if period_match:
            period_start = convert_date(period_match.group(1))
            period_end = convert_date(period_match.group(2))
            continue

        # SOLDE AU : DD/MM/YYYY ... amount
        if "SOLDE AU" in full_line:
            m = re.search(
                r"SOLDE AU\s*:\s*\d{2}/\d{2}/\d{4}\s+([\d ]+,\d{2})", full_line
            )
            if m:
                solde_initial = parse_amount(m.group(1))
            continue

        # Nouveau solde
        if "Nouveau solde" in full_line:
            m = re.search(r"(\d[\d ]{0,15},\d{2})\s*$", full_line)
            if m:
                solde_final = parse_amount(m.group(1))
            continue

        # --- Transaction line (starts with date DD/MM/YYYY) ---
        tx_match = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.+)", full_line)
        if tx_match:
            # Save previous transaction
            if current_tx:
                transactions.append(current_tx)

            date_op = tx_match.group(1)
            rest = tx_match.group(2)

            parsed = _parse_transaction_line(full_line, rest)
            if parsed:
                current_tx = {
                    "date_operation": convert_date(date_op),
                    "date_valeur": parsed["date_valeur"],
                    "libelle": parsed["libelle"].strip(),
                    "montant": parsed["montant"],
                }
            else:
                # Not a valid transaction (header line, etc.) — skip
                current_tx = None
            continue

        # --- Non-transaction lines below ---

        # Skip headers/footers
        if any(skip in stripped for skip in SKIP_PATTERNS):
            continue

        # Skip column header "Date" (appears alone on page breaks)
        if stripped == "Date":
            continue

        # Continuation line — must contain letters and not be pure numbers
        if current_tx and stripped and re.search(r"[a-zA-ZÀ-ÿ]", stripped):
            if not re.match(r"^[\d\s,\.¤%]+$", stripped):
                current_tx["libelle"] += " " + stripped
            continue

    # Last transaction
    if current_tx:
        transactions.append(current_tx)

    if not transactions:
        return {"ok": False, "error": "Aucune transaction trouvée dans le PDF"}

    return {
        "ok": True,
        "transactions": transactions,
        "period_start": period_start,
        "period_end": period_end,
        "solde_initial": solde_initial,
        "solde_final": solde_final,
        "count": len(transactions),
    }


def _parse_transaction_line(full_line: str, rest: str) -> dict | None:
    """Parse everything after date_operation.

    Uses absolute position in the full line to determine debit vs credit.
    Returns None if line is not a valid transaction (e.g. page header).
    """
    # Find date_valeur (DD/MM/YYYY) followed by an amount at end of line
    match = re.search(
        r"(\d{2}/\d{2}/\d{4})\s+([\d\s]+,\d{2})\s*$",
        rest,
    )
    if not match:
        return None

    date_valeur = convert_date(match.group(1))
    libelle = rest[: match.start()].strip()
    amount = parse_amount(match.group(2))

    # Find position of the amount's first digit in the FULL line
    # rest starts at position (len(full_line) - len(rest)) in full_line
    rest_offset = len(full_line) - len(rest)
    amount_pos = rest_offset + match.start(2)

    if amount_pos >= CREDIT_COLUMN_THRESHOLD:
        montant = amount  # Credit (positive)
    else:
        montant = -amount  # Debit (negative)

    return {
        "date_valeur": date_valeur,
        "libelle": libelle,
        "montant": montant,
    }
