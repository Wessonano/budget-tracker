"""Budget Tracker — aiohttp server."""

import hashlib
import os

import aiohttp_jinja2
import jinja2
from aiohttp import web
from dotenv import load_dotenv

from categorizer import categorize_transactions
from db import (
    get_categories,
    get_import_by_hash,
    get_import_history,
    get_months,
    get_transactions,
    init_db,
    insert_import,
    insert_transactions,
)
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
        )
        insert_transactions(db, import_id, transactions)

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


async def dashboard_redirect(request):
    """GET / — Redirect to /import for Phase 1."""
    raise web.HTTPFound("/import")


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


def create_app():
    app = web.Application(client_max_size=5 * 1024 * 1024)

    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("templates"))

    app.router.add_static("/static/", path="static", name="static")

    app.router.add_get("/", dashboard_redirect)
    app.router.add_get("/import", import_page)
    app.router.add_post("/import", import_upload)
    app.router.add_get("/api/dashboard", api_dashboard)
    app.router.add_get("/api/months", api_months)

    return app


if __name__ == "__main__":
    db = init_db(DATA_DIR)
    app = create_app()
    print(f"Budget Tracker running on http://{HOST}:{PORT}")
    web.run_app(app, host=HOST, port=PORT)
