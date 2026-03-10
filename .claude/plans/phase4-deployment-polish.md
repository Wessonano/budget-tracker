# Feature: Phase 4 — Déploiement LXC + PWA + Polish

The following plan should be complete. Validate documentation and codebase patterns before implementing.

Pay special attention to naming of existing utils, types and models. Import from the right files. Mirror the aitime LXC setup pattern exactly.

## Feature Description

Phase 4 deploys Budget Tracker to a Proxmox LXC container (Debian 12) behind a Cloudflare tunnel (`budget.nanoserveur.fr`), adds PWA support for installability on phone, creates a deployment script for rsync from Mac Mini, and adds E2E test infrastructure. This is the final phase — after this, the app is production-ready.

## User Story

As Arnaud
I want to access Budget Tracker from anywhere via `budget.nanoserveur.fr`, install it as an app on my phone, and have a repeatable deployment process
So that the app is always available, feels native on mobile, and can be updated easily

## Problem Statement

Budget Tracker runs locally on the Mac Mini but is not accessible externally. There's no LXC container, no tunnel, no PWA manifest. Deploying changes requires manual steps. The father's share page (`/share/<token>`) needs a public URL to be useful.

## Solution Statement

Create an LXC 105 on Proxmox following the aitime pattern (Debian 12, 1 core, 512 MB RAM), deploy the app with systemd + cloudflared tunnel to `budget.nanoserveur.fr`, add a PWA manifest for phone installability, create a `scripts/deploy-budget.sh` script for one-command deployment from Mac Mini, and document the full setup process.

## Feature Metadata

**Feature Type**: Deployment / Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: Infrastructure (Proxmox LXC), app.py (PWA manifest route), templates (manifest link), scripts (deploy + setup)
**Dependencies**: Proxmox host access, Cloudflare account (already configured for nanoserveur.fr), poppler-utils (pdftotext)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ BEFORE IMPLEMENTING

- `/Users/arnaud/mon-assistant/scripts/setup-aitime-lxc.sh` (full file) — Why: **Exact pattern to mirror** for LXC creation, systemd service, cloudflared setup, SSH
- `/Users/arnaud/mon-assistant/scripts/setup-le-trio-lxc.sh` (full file) — Why: Alternative LXC pattern with Caddy (don't use Caddy, but see tunnel setup)
- `app.py` (lines 353-385) — Why: `create_app()` + `__main__` block — need to add static manifest route + meta tags
- `templates/base.html` (full file) — Why: Need to add PWA `<link rel="manifest">` + meta tags in `<head>`
- `requirements.txt` — Why: All deps must be installed in LXC venv
- `.env.example` — Why: Env vars to configure in LXC
- `.gitignore` — Why: Verify scripts/ not ignored

### New Files to Create

- `scripts/setup-budget-lxc.sh` — LXC creation script (run on Proxmox host)
- `scripts/deploy-budget.sh` — Deployment script (run on Mac Mini, rsync to LXC)
- `static/manifest.json` — PWA manifest
- `static/icons/icon-192.png` — PWA icon 192x192
- `static/icons/icon-512.png` — PWA icon 512x512
- `static/sw.js` — Service worker (minimal, for PWA installability)

### Files to Modify

- `app.py` — Add service worker route
- `templates/base.html` — Add PWA meta tags + manifest link + SW registration

### Relevant Documentation

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
  - Tunnel creation and DNS routing
  - Why: Reference for tunnel config
- [PWA Web App Manifest](https://developer.mozilla.org/en-US/docs/Web/Manifest)
  - Manifest fields: name, short_name, icons, start_url, display, theme_color, background_color
  - Why: Minimum fields for installability
- [Service Worker Registration](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerContainer/register)
  - Why: Minimal SW needed for Chrome install prompt

### Patterns to Follow

**LXC Setup Pattern** (from `setup-aitime-lxc.sh`):
```bash
CTID=105
HOSTNAME="budget"
IP="192.168.1.105/24"
# Same structure: check Proxmox → template → create LXC → packages → venv → systemd → cloudflared → SSH
```

**systemd Service Pattern** (from aitime):
```ini
[Service]
Type=simple
User=root
WorkingDirectory=/opt/budget-tracker
Environment=DATA_DIR=/opt/budget-tracker/data
Environment=PORT=8080
ExecStart=/opt/budget-tracker/venv/bin/python3 /opt/budget-tracker/app.py
Restart=always
RestartSec=5
```

**Deploy Pattern** (from `sync-blog.sh` / `deploy.sh`):
```bash
rsync -avz --delete --exclude='.git' --exclude='venv' --exclude='data' \
  /Users/arnaud/mon-assistant/memory/projects/budget-tracker/ \
  root@192.168.1.105:/opt/budget-tracker/
ssh root@192.168.1.105 "systemctl restart budget-tracker"
```

**Color Scheme** (from `static/css/style.css`):
```
Background: #1a1a2e
Accent: #e94560
```

---

## IMPLEMENTATION PLAN

### Phase 1: PWA Support (local changes)

Add PWA manifest, icons, service worker, and meta tags so the app is installable on mobile. This is done before deployment so it's included in the first deploy.

### Phase 2: LXC Setup Script

Create `scripts/setup-budget-lxc.sh` mirroring `setup-aitime-lxc.sh` exactly, with budget-tracker-specific differences (poppler-utils, more deps, .env setup).

### Phase 3: Deployment Script

Create `scripts/deploy-budget.sh` for one-command rsync from Mac Mini to LXC, with service restart and health check.

### Phase 4: Polish & Documentation

Ensure the uncommitted `app.py` fix is included, update `.env.example` if needed, verify all tests pass.

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `static/manifest.json` — PWA manifest

- **IMPLEMENT**: Minimal PWA manifest for installability
- **PATTERN**: Standard PWA fields matching the app's dark theme
- **CONTENT**:
```json
{
  "name": "Budget Tracker",
  "short_name": "Budget",
  "description": "Suivi budgétaire BoursoBank",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#e94560",
  "icons": [
    {
      "src": "/static/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```
- **VALIDATE**: `python3 -c "import json; json.load(open('static/manifest.json')); print('OK')"`

### Task 2: CREATE `static/icons/` — PWA icons

- **IMPLEMENT**: Generate simple budget-themed icons (192x192 and 512x512 PNG)
- **APPROACH**: Use Python + pillow to generate simple icons with the accent color (#e94560) and a "₿" or "€" symbol on dark background (#1a1a2e). Or create simple colored squares if pillow isn't available.
- **ALTERNATIVE**: Use an SVG icon inline if PNG generation is complex — but manifest requires PNG
- **GOTCHA**: Icons must be exact sizes (192x192 and 512x512) for Chrome installability
- **VALIDATE**: `file static/icons/icon-192.png && file static/icons/icon-512.png`

### Task 3: CREATE `static/sw.js` — Minimal service worker

- **IMPLEMENT**: Bare minimum service worker for PWA installability (Chrome requires a SW to show install prompt)
- **CONTENT**:
```javascript
// Minimal service worker for PWA installability
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
```
- **GOTCHA**: Do NOT add caching — the app uses live data, caching would cause stale budget numbers
- **VALIDATE**: `cat static/sw.js | head -3`

### Task 4: UPDATE `templates/base.html` — Add PWA meta tags

- **IMPLEMENT**: Add to `<head>`:
  - `<link rel="manifest" href="/static/manifest.json">`
  - `<meta name="theme-color" content="#e94560">`
  - `<meta name="apple-mobile-web-app-capable" content="yes">`
  - `<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">`
  - `<link rel="apple-touch-icon" href="/static/icons/icon-192.png">`
- **IMPLEMENT**: Add SW registration script before `</body>`:
```html
<script>
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/sw.js');
}
</script>
```
- **PATTERN**: Follow existing `base.html` structure — add meta tags in `<head>` block, script at end
- **GOTCHA**: The manifest href must be `/static/manifest.json` (aiohttp serves `/static/` as static dir)
- **VALIDATE**: Start app locally, open in Chrome DevTools → Application → Manifest (should show parsed manifest)

### Task 5: CREATE `scripts/setup-budget-lxc.sh` — LXC creation script

- **IMPLEMENT**: Mirror `setup-aitime-lxc.sh` exactly with these differences:
  - `CTID=105`, `HOSTNAME="budget"`, `IP="192.168.1.105/24"`
  - **Extra package**: `poppler-utils` (for `pdftotext`)
  - **Venv deps**: `pip install aiohttp aiohttp-jinja2 aiofiles python-dotenv` (from requirements.txt)
  - **App dir**: `/opt/budget-tracker/` (with `data/`, `uploads/`, `static/`, `templates/` subdirs)
  - **systemd service name**: `budget-tracker.service`
  - **Environment vars**: `DATA_DIR=/opt/budget-tracker/data`, `PORT=8080`, `HOST=0.0.0.0`
  - **cloudflared tunnel name**: `budget`, DNS route: `budget.nanoserveur.fr`
- **STRUCTURE** (same 13 sections as aitime):
  1. Check Proxmox
  2. Check template
  3. Create LXC (skip if exists)
  4. Start LXC
  5. Install packages (python3, python3-pip, python3-venv, openssh-server, curl, **poppler-utils**)
  6. Setup app directory (`/opt/budget-tracker/{data,static,templates}`)
  7. Create venv + install deps
  8. Create .env file (placeholder for DISCORD_WEBHOOK_BUDGET, SHARE_TOKEN)
  9. Create systemd service `budget-tracker.service`
  10. Install cloudflared
  11. Cloudflared tunnel instructions (interactive)
  12. Create cloudflared.service
  13. SSH setup + summary with next steps
- **GOTCHA**: Don't create a placeholder app.py — the deploy script will rsync the real code
- **GOTCHA**: Must include `poppler-utils` or `pdftotext` will fail at runtime
- **VALIDATE**: `bash -n scripts/setup-budget-lxc.sh` (syntax check)

### Task 6: CREATE `scripts/deploy-budget.sh` — Deployment script

- **IMPLEMENT**: One-command deploy from Mac Mini to LXC 105
- **PATTERN**: Mirror `scripts/deploy.sh` (le-trio) with rsync + SSH
- **CONTENT**:
```bash
#!/bin/bash
# deploy-budget.sh — Deploy Budget Tracker to LXC 105
# Run from Mac Mini: bash scripts/deploy-budget.sh

set -euo pipefail

LXC_HOST="root@192.168.1.105"
APP_DIR="/opt/budget-tracker"
LOCAL_DIR="/Users/arnaud/mon-assistant/memory/projects/budget-tracker"

echo "🚀 Deploying Budget Tracker to LXC 105..."

# Check SSH connectivity
if ! ssh -o ConnectTimeout=5 $LXC_HOST true 2>/dev/null; then
    echo "❌ Cannot reach $LXC_HOST — is LXC 105 running?"
    exit 1
fi

# Rsync app files (exclude data, venv, git, PDFs, caches)
rsync -avz --delete \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='data' \
    --exclude='__pycache__' \
    --exclude='.env' \
    --exclude='*.pdf' \
    --exclude='e2e-screenshots' \
    --exclude='test_e2e_data' \
    --exclude='.claude' \
    "$LOCAL_DIR/" "$LXC_HOST:$APP_DIR/"

# Restart service
ssh $LXC_HOST "systemctl restart budget-tracker"

# Wait + health check
sleep 2
STATUS=$(ssh $LXC_HOST "systemctl is-active budget-tracker" || true)
if [ "$STATUS" = "active" ]; then
    echo "✅ Budget Tracker deployed and running"
    echo "   Local: http://192.168.1.105:8080"
    echo "   Public: https://budget.nanoserveur.fr"
else
    echo "❌ Service not running — check logs:"
    echo "   ssh $LXC_HOST journalctl -u budget-tracker -n 20"
    exit 1
fi
```
- **GOTCHA**: Exclude `data/` (contains budget.db — never overwrite production DB), exclude `.env` (has production secrets), exclude `*.pdf` (uploaded statements stay on server)
- **GOTCHA**: Exclude `.claude/` (plans, skills — not needed in production)
- **VALIDATE**: `bash -n scripts/deploy-budget.sh` (syntax check)

### Task 7: UPDATE `app.py` — Ensure uncommitted fix is clean

- **IMPLEMENT**: The current diff in `app.py` (budgets_create fix) is correct. No additional changes needed to app.py beyond what's already modified.
- **VERIFY**: The fix correctly handles `budget_id` before `category_id` to prevent edit from being blocked by `category_id=0`
- **VALIDATE**: `cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker && python3 -m pytest tests/ -v`

### Task 8: UPDATE `.env.example` — Add deployment notes

- **IMPLEMENT**: Add comments for production deployment context
- **CONTENT**:
```
# Server
PORT=8080
HOST=0.0.0.0
DATA_DIR=./data

# Discord alerts (optional — leave empty to disable)
DISCORD_WEBHOOK_BUDGET=

# Share token for father's read-only page (auto-generated if empty)
SHARE_TOKEN=
```
- **VALIDATE**: `cat .env.example`

---

## TESTING STRATEGY

### Unit Tests

Existing tests in `tests/test_parser.py` and `tests/test_budgets.py` cover all backend logic. Run them to ensure no regression.

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
source venv/bin/activate
python3 -m pytest tests/ -v
```

### Integration Test (local)

Start the app locally and verify:
```bash
source venv/bin/activate
python3 app.py &
sleep 2
# Dashboard loads
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/
# Manifest loads
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/static/manifest.json
# SW loads
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/static/sw.js
# Kill server
kill %1
```

### E2E Tests (agent-browser)

After deployment, run the E2E test plan from the PRD (Section 13, Phase 4):

1. **T4.1 — Accès public**: Open `https://budget.nanoserveur.fr`, verify dashboard loads via tunnel
2. **T4.2 — Import en production**: Upload a PDF on the production URL
3. **T4.3 — Partage en production**: Open `https://budget.nanoserveur.fr/share/<token>`, verify public access
4. **T4.4 — PWA install**: Open on mobile, verify install prompt and manifest detection
5. **T4.5 — Smoke test**: Full flow (Import → Dashboard → Transactions → Correct category → Create envelope → Share)

---

## VALIDATION COMMANDS

### Level 1: Syntax & Lint

```bash
# Python syntax check
python3 -m py_compile app.py
python3 -m py_compile db.py
python3 -m py_compile parser.py
python3 -m py_compile categorizer.py
python3 -m py_compile notifications.py

# Shell script syntax check
bash -n scripts/setup-budget-lxc.sh
bash -n scripts/deploy-budget.sh

# JSON validation
python3 -c "import json; json.load(open('static/manifest.json')); print('manifest OK')"
```

### Level 2: Unit Tests

```bash
cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker
source venv/bin/activate
python3 -m pytest tests/ -v
```

### Level 3: Local Integration

```bash
# Start app, check routes, check PWA assets
source venv/bin/activate
python3 app.py &
PID=$!
sleep 2
curl -sf http://localhost:8080/ > /dev/null && echo "Dashboard OK" || echo "Dashboard FAIL"
curl -sf http://localhost:8080/static/manifest.json > /dev/null && echo "Manifest OK" || echo "Manifest FAIL"
curl -sf http://localhost:8080/static/sw.js > /dev/null && echo "SW OK" || echo "SW FAIL"
curl -sf http://localhost:8080/import > /dev/null && echo "Import OK" || echo "Import FAIL"
curl -sf http://localhost:8080/budgets > /dev/null && echo "Budgets OK" || echo "Budgets FAIL"
kill $PID
```

### Level 4: Production (post-deploy)

```bash
# After deploying to LXC 105
ssh root@192.168.1.105 "systemctl is-active budget-tracker"
ssh root@192.168.1.105 "curl -sf http://localhost:8080/ > /dev/null && echo OK"
curl -sf https://budget.nanoserveur.fr/ > /dev/null && echo "Tunnel OK" || echo "Tunnel FAIL"
```

---

## ACCEPTANCE CRITERIA

- [ ] `scripts/setup-budget-lxc.sh` creates LXC 105 with all dependencies (Python, poppler-utils, venv, systemd, cloudflared)
- [ ] `scripts/deploy-budget.sh` deploys from Mac Mini to LXC via rsync + restarts service
- [ ] PWA manifest at `/static/manifest.json` is valid and detected by Chrome
- [ ] Service worker at `/static/sw.js` registers without errors
- [ ] App installable on phone (Chrome "Add to Home Screen" prompt)
- [ ] `templates/base.html` includes manifest link, theme-color, apple-mobile-web-app meta tags
- [ ] All existing unit tests pass (`pytest tests/ -v`)
- [ ] App starts and serves all routes locally
- [ ] Shell scripts pass syntax check (`bash -n`)
- [ ] Icons exist at correct sizes (192x192, 512x512)
- [ ] Deploy script excludes `data/`, `.env`, `*.pdf`, `venv/`, `.git/`

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1 through 8)
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully (Level 1-3)
- [ ] Full test suite passes
- [ ] No linting or syntax errors
- [ ] Local integration test confirms all routes work
- [ ] Shell scripts are executable and syntax-valid
- [ ] Commit all changes

---

## NOTES

### LXC ID Decision
**LXC 105** chosen (next sequential after Le Trio at 104). Available IDs: 101, 105-109. Chose 105 to keep numbering clean.

### IP Address
**192.168.1.105/24** — follows the pattern where LXC ID matches last octet.

### Why No Caching in Service Worker
Budget data changes with every import. A caching SW would show stale numbers. The SW is minimal — just enough for Chrome to show the install prompt. No offline support (the app needs the DB).

### Deploy Script vs Sync Script
Unlike `sync-aitime.sh` (periodic sync of a single data file), `deploy-budget.sh` is a full app deploy (all Python + templates + static). It's run manually after code changes, not on a cron. No launchd plist needed.

### What Requires Manual Steps (cannot be automated)
1. **Cloudflared tunnel login** — requires browser authentication on Cloudflare
2. **SSH key copy** — `ssh-copy-id root@192.168.1.105` from Mac Mini
3. **`.env` configuration** — DISCORD_WEBHOOK_BUDGET and SHARE_TOKEN must be set manually in production
4. **Running the setup script** — must be run on Proxmox host directly

### Production .env
On the LXC, `/opt/budget-tracker/.env` should contain:
```
PORT=8080
HOST=0.0.0.0
DATA_DIR=/opt/budget-tracker/data
DISCORD_WEBHOOK_BUDGET=<webhook_url_from_discord>
SHARE_TOKEN=<generated_or_chosen_uuid>
```

### Untracked PDF
`Releve-compte-27-02-2026-1.pdf` in the repo root is a new statement to import — do NOT commit it. It's already in `.gitignore` pattern but with a `-1` suffix. Verify `.gitignore` handles it.
