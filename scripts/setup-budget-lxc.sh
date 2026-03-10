#!/bin/bash
# =============================================================================
# setup-budget-lxc.sh — Setup LXC 105 on Proxmox for Budget Tracker
# =============================================================================
# Run on Proxmox host: bash setup-budget-lxc.sh
#
# Creates:
#   - LXC 105 (Debian 12, 1 core, 512 MB RAM, 4 GB disk)
#   - IP: 192.168.1.105/24
#   - app.py (aiohttp, port 8080) served via systemd
#   - cloudflared tunnel → budget.nanoserveur.fr
#
# After running this script:
#   1. Deploy with: bash scripts/deploy-budget.sh (from Mac Mini)
#   2. Configure cloudflared tunnel (interactive login)
#   3. Set .env values (DISCORD_WEBHOOK_BUDGET, SHARE_TOKEN)
# =============================================================================

set -euo pipefail

CTID=105
HOSTNAME="budget"
IP="192.168.1.105/24"
GW="192.168.1.254"
DNS="1.1.1.1"
CORES=1
MEMORY=512
DISK=4
STORAGE="local-lvm"
TEMPLATE="local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC} $1"; }
fail() { echo -e "${RED}[KO]${NC} $1"; }
info() { echo -e "${BLUE}[..]${NC} $1"; }

echo ""
echo "============================================="
echo "  Budget Tracker — LXC $CTID Setup"
echo "  Hostname: $HOSTNAME"
echo "  IP: $IP"
echo "============================================="
echo ""

# =============================================================================
# 1. Check we're on Proxmox
# =============================================================================
if ! command -v pct &>/dev/null; then
    fail "This script must be run on a Proxmox host"
    exit 1
fi
ok "Running on Proxmox"

# =============================================================================
# 2. Check template exists
# =============================================================================
if ! pveam list local | grep -q "debian-12-standard"; then
    info "Downloading Debian 12 template..."
    pveam download local debian-12-standard_12.7-1_amd64.tar.zst
fi
ok "Debian 12 template available"

# =============================================================================
# 3. Create LXC (skip if exists)
# =============================================================================
if pct status $CTID &>/dev/null; then
    warn "LXC $CTID already exists — skipping creation"
else
    info "Creating LXC $CTID..."
    pct create $CTID $TEMPLATE \
        --hostname $HOSTNAME \
        --cores $CORES \
        --memory $MEMORY \
        --rootfs ${STORAGE}:${DISK} \
        --net0 name=eth0,bridge=vmbr0,ip=$IP,gw=$GW \
        --nameserver $DNS \
        --unprivileged 1 \
        --features nesting=1 \
        --start 0
    ok "LXC $CTID created"
fi

# =============================================================================
# 4. Start LXC
# =============================================================================
if [ "$(pct status $CTID | awk '{print $2}')" != "running" ]; then
    pct start $CTID
    sleep 3
fi
ok "LXC $CTID running"

# =============================================================================
# 5. Install packages (includes poppler-utils for pdftotext)
# =============================================================================
info "Installing packages..."
pct exec $CTID -- bash -c "
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv openssh-server curl poppler-utils > /dev/null 2>&1
"
ok "Packages installed (incl. poppler-utils)"

# =============================================================================
# 6. Setup app directory
# =============================================================================
info "Setting up app directory..."
pct exec $CTID -- bash -c "
    mkdir -p /opt/budget-tracker/{data,static,templates}
"
ok "App directory structure ready"

# =============================================================================
# 7. Create venv + install deps
# =============================================================================
info "Creating venv and installing dependencies..."
pct exec $CTID -- bash -c "
    cd /opt/budget-tracker
    python3 -m venv venv
    venv/bin/pip install --quiet aiohttp aiohttp-jinja2 aiofiles python-dotenv
"
ok "Venv + dependencies installed"

# =============================================================================
# 8. Create .env file (placeholder values)
# =============================================================================
info "Creating .env with placeholder values..."
pct exec $CTID -- bash -c "
    cat > /opt/budget-tracker/.env << 'EOF'
PORT=8080
HOST=0.0.0.0
DATA_DIR=/opt/budget-tracker/data

# Discord alerts (set webhook URL to enable)
DISCORD_WEBHOOK_BUDGET=

# Share token for father's read-only page
SHARE_TOKEN=
EOF
"
ok ".env created — edit with production values later"

# =============================================================================
# 9. Create systemd service
# =============================================================================
info "Creating budget-tracker.service..."
pct exec $CTID -- bash -c "
    cat > /etc/systemd/system/budget-tracker.service << 'EOF'
[Unit]
Description=Budget Tracker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/budget-tracker
Environment=DATA_DIR=/opt/budget-tracker/data
Environment=PORT=8080
Environment=HOST=0.0.0.0
ExecStart=/opt/budget-tracker/venv/bin/python3 /opt/budget-tracker/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable budget-tracker.service
"
ok "budget-tracker.service created + enabled"

# =============================================================================
# 10. Install cloudflared
# =============================================================================
info "Installing cloudflared..."
pct exec $CTID -- bash -c "
    ARCH=\$(dpkg --print-architecture)
    curl -fsSL -o /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-\${ARCH}
    chmod +x /usr/local/bin/cloudflared
"
ok "cloudflared installed"

# =============================================================================
# 11. Cloudflared tunnel setup instructions
# =============================================================================
info "Cloudflared tunnel setup..."
echo ""
echo "  Run these commands inside LXC $CTID to setup the tunnel:"
echo ""
echo "  pct enter $CTID"
echo "  cloudflared tunnel login"
echo "  cloudflared tunnel create budget"
echo "  cloudflared tunnel route dns budget budget.nanoserveur.fr"
echo ""
echo "  Then create the config:"
echo ""
echo "  mkdir -p /root/.cloudflared"
echo "  cat > /root/.cloudflared/config.yml << 'EOF'"
echo "  tunnel: budget"
echo "  credentials-file: /root/.cloudflared/<TUNNEL-ID>.json"
echo "  ingress:"
echo "    - hostname: budget.nanoserveur.fr"
echo "      service: http://localhost:8080"
echo "    - service: http_status:404"
echo "  EOF"
echo ""

# =============================================================================
# 12. Create cloudflared systemd service
# =============================================================================
info "Creating cloudflared.service..."
pct exec $CTID -- bash -c "
    cat > /etc/systemd/system/cloudflared.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel run budget
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable cloudflared.service
"
ok "cloudflared.service created + enabled"

# =============================================================================
# 13. SSH key setup for rsync from Mac Mini
# =============================================================================
info "SSH setup..."
pct exec $CTID -- bash -c "
    systemctl enable ssh
    systemctl start ssh
    mkdir -p /root/.ssh
    chmod 700 /root/.ssh
    touch /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
"
echo ""
echo "  Add Mac Mini SSH key to LXC $CTID:"
echo "  ssh-copy-id root@192.168.1.105"
echo ""
ok "SSH ready — add Mac Mini public key"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================="
echo "  LXC $CTID ($HOSTNAME) setup complete!"
echo "============================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Add Mac Mini SSH key:"
echo "     ssh-copy-id root@192.168.1.105"
echo ""
echo "  2. Deploy the app from Mac Mini:"
echo "     cd /Users/arnaud/mon-assistant/memory/projects/budget-tracker"
echo "     bash scripts/deploy-budget.sh"
echo ""
echo "  3. Set production .env values:"
echo "     ssh root@192.168.1.105 'nano /opt/budget-tracker/.env'"
echo ""
echo "  4. Setup cloudflared tunnel (see above)"
echo "     pct exec $CTID -- systemctl start cloudflared"
echo ""
echo "  5. Test locally:"
echo "     curl http://192.168.1.105:8080/"
echo ""
echo "  6. Test via tunnel:"
echo "     curl https://budget.nanoserveur.fr/"
echo ""
