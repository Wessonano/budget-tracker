"""Budget Tracker — aiohttp server."""

import hashlib
import os
import re
import uuid

import aiohttp_jinja2
import jinja2
from aiohttp import web
from dotenv import load_dotenv

from categorizer import categorize_transactions
from db import (
    delete_budget,
    get_budget_by_id,
    get_budgets_with_spending,
    get_categories,
    get_daily_balances,
    get_import_by_hash,
    get_import_history,
    get_month_comparison,
    get_month_summary,
    get_months,
    get_setting,
    get_solde_initial,
    get_top_expenses,
    get_transaction_by_id,
    get_transactions,
    init_db,
    insert_budget,
    insert_import,
    insert_learned_pattern,
    insert_transactions,
    previous_month,
    set_setting,
    update_budget,
    update_transaction_category,
)
from notifications import check_and_send_alerts
from parser import parse_boursobank

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "./data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
PORT = int(os.getenv("PORT", 8080))
HOST = os.getenv("HOST", "0.0.0.0")

db = None


async def import_page(request):
    """GET /import — Upload page with import history."""
    imports = get_import_history(db)
    return aiohttp_jinja2.render_template(
        "import.html", request, {"active": "import", "imports": imports}
    )


async def import_upload(request):
    """POST /import — Upload + parse PDF."""
    reader = await request.multipart()
    field = await reader.next()

    if not field or field.name != "file":
        return _render_import(request, {"ok": False, "error": "Aucun fichier envoyé"})

    filename = field.filename
    if not filename or not filename.lower().endswith(".pdf"):
        return _render_import(
            request, {"ok": False, "error": "Le fichier doit être un PDF"}
        )

    data = await field.read()

    if len(data) > 5 * 1024 * 1024:
        return _render_import(
            request, {"ok": False, "error": "Fichier trop volumineux (max 5 Mo)"}
        )

    # Deduplication via SHA256
    sha256 = hashlib.sha256(data).hexdigest()
    if get_import_by_hash(db, sha256):
        return _render_import(
            request, {"ok": False, "error": "Ce relevé a déjà été importé"}
        )

    # Save PDF
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    pdf_path = os.path.join(UPLOAD_DIR, f"{sha256}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(data)

    try:
        # Parse
        result = parse_boursobank(pdf_path)
        if not result["ok"]:
            os.remove(pdf_path)
            return _render_import(request, result)

        # Categorize
        transactions = categorize_transactions(result["transactions"], db)

        # Insert in DB
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
        insert_transactions(db, import_id, transactions)

        # Check budget alerts
        try:
            alert_month = result.get("period_start", "")[:7] if result.get("period_start") else None
            if alert_month:
                budgets_data = get_budgets_with_spending(db, alert_month)
                await check_and_send_alerts(budgets_data)
        except Exception:
            pass  # Don't fail import because of alert errors

        return _render_import(request, result)
    except Exception as e:
        # Cleanup orphaned PDF on any failure
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return _render_import(
            request, {"ok": False, "error": f"Erreur lors de l'import : {e}"}
        )


def _render_import(request, result):
    """Helper to render import page with result and history."""
    return aiohttp_jinja2.render_template(
        "import.html",
        request,
        {"active": "import", "result": result, "imports": get_import_history(db)},
    )


async def dashboard_page(request):
    """GET / — Dashboard mensuel."""
    months = get_months(db)
    month = request.query.get("month")
    if not month:
        month = months[0] if months else None

    if not month:
        return aiohttp_jinja2.render_template(
            "dashboard.html",
            request,
            {"active": "dashboard", "month": None, "months": months},
        )

    summary = get_month_summary(db, month)
    solde_initial = get_solde_initial(db, month)
    daily_balances = get_daily_balances(db, month, solde_initial or 0)
    top_expenses = get_top_expenses(db, month)
    prev_month = previous_month(month)
    comparison = get_month_comparison(db, month, prev_month) if prev_month in months else []

    return aiohttp_jinja2.render_template(
        "dashboard.html",
        request,
        {
            "active": "dashboard",
            "month": month,
            "months": months,
            "summary": summary,
            "solde_initial": solde_initial,
            "daily_balances": daily_balances,
            "top_expenses": top_expenses,
            "comparison": comparison,
        },
    )


async def transactions_page(request):
    """GET /transactions — Liste des transactions."""
    months = get_months(db)
    month = request.query.get("month")
    if not month:
        month = months[0] if months else None

    transactions = get_transactions(db, month) if month else []
    categories = get_categories(db)

    return aiohttp_jinja2.render_template(
        "transactions.html",
        request,
        {
            "active": "transactions",
            "month": month,
            "months": months,
            "transactions": transactions,
            "categories": categories,
        },
    )


async def api_update_category(request):
    """POST /api/transactions/{id}/category — Change category + learn pattern."""
    tx_id = int(request.match_info["id"])
    data = await request.json()
    new_category_id = data.get("category_id")

    if not new_category_id:
        return web.json_response(
            {"ok": False, "error": "category_id required"}, status=400
        )

    tx = get_transaction_by_id(db, tx_id)
    if not tx:
        return web.json_response(
            {"ok": False, "error": "Transaction not found"}, status=404
        )

    # Update category
    update_transaction_category(db, tx_id, new_category_id)

    # Learn pattern from libelle
    pattern = _extract_pattern(tx["libelle"])
    if pattern:
        insert_learned_pattern(db, new_category_id, pattern)

    # Return updated transaction
    updated_tx = get_transaction_by_id(db, tx_id)
    return web.json_response({"ok": True, "transaction": updated_tx})


def _extract_pattern(libelle: str) -> str | None:
    """Extract a reusable pattern from a transaction libelle.

    Examples:
    - 'CARTE 30/01/26 AGENALINE CB*0403' -> 'AGENALINE'
    - 'VIR Virement depuis BoursoBank M LARRIEU ERICK' -> 'LARRIEU ERICK'
    - 'PRLV FREE MOBILE' -> 'FREE MOBILE'
    """
    clean = libelle.upper()
    clean = re.sub(r"CARTE\s+\d{2}/\d{2}/\d{2,4}\s+", "", clean)
    clean = re.sub(r"\s*CB\*\d+", "", clean)
    clean = re.sub(r"^(VIR INST|VIR|PRLV)\s+", "", clean)
    clean = re.sub(r"VIREMENT DEPUIS BOURSOBANK\s*", "", clean)
    clean = re.sub(r"R[EE]F\s*:.*", "", clean)
    clean = clean.strip()
    if len(clean) < 3:
        return None
    return clean


async def api_dashboard(request):
    """GET /api/dashboard?month=YYYY-MM — Dashboard data as JSON."""
    month = request.query.get("month")
    if not month:
        months = get_months(db)
        month = months[0] if months else None

    if not month:
        return web.json_response({"transactions": [], "categories": []})

    transactions = get_transactions(db, month)
    categories = get_categories(db)

    return web.json_response(
        {"month": month, "transactions": transactions, "categories": categories}
    )


async def api_months(request):
    """GET /api/months — List of available months."""
    return web.json_response({"months": get_months(db)})


async def budgets_page(request):
    """GET /budgets — Envelopes management page."""
    months = get_months(db)
    month = request.query.get("month")
    if not month:
        month = months[0] if months else None

    budgets = get_budgets_with_spending(db, month) if month else []
    categories = get_categories(db)
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
    budget_id = data.get("budget_id")

    if budget_id and amount_max > 0:
        update_budget(db, int(budget_id), amount_max)
    elif category_id and amount_max > 0:
        insert_budget(db, category_id, amount_max)

    month = data.get("month", "")
    raise web.HTTPFound(f"/budgets?month={month}" if month else "/budgets")


async def budgets_delete_handler(request):
    """POST /api/budgets/{id}/delete — Delete a budget envelope."""
    budget_id = int(request.match_info["id"])
    delete_budget(db, budget_id)
    return web.json_response({"ok": True})


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


def create_app():
    app = web.Application(client_max_size=5 * 1024 * 1024)

    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("templates"))

    app.router.add_static("/static/", path="static", name="static")

    app.router.add_get("/", dashboard_page)
    app.router.add_get("/transactions", transactions_page)
    app.router.add_get("/import", import_page)
    app.router.add_post("/import", import_upload)
    app.router.add_get("/api/dashboard", api_dashboard)
    app.router.add_get("/api/months", api_months)
    app.router.add_post("/api/transactions/{id}/category", api_update_category)
    app.router.add_get("/budgets", budgets_page)
    app.router.add_post("/budgets", budgets_create)
    app.router.add_post("/api/budgets/{id}/delete", budgets_delete_handler)
    app.router.add_get("/share/{token}", share_page)

    return app


if __name__ == "__main__":
    db = init_db(DATA_DIR)
    if not get_setting(db, "share_token"):
        token = os.getenv("SHARE_TOKEN") or str(uuid.uuid4())
        set_setting(db, "share_token", token)
        print(f"Share URL: http://{HOST}:{PORT}/share/{token}")
    else:
        print(f"Share URL: http://{HOST}:{PORT}/share/{get_setting(db, 'share_token')}")
    app = create_app()
    print(f"Budget Tracker running on http://{HOST}:{PORT}")
    web.run_app(app, host=HOST, port=PORT)
