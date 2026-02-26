#!/usr/bin/env bash
# deploy.sh — Deploy LabClaw to a remote server
# Usage: LABCLAW_REMOTE=my-server bash deploy/deploy.sh
# Optional: LABCLAW_DOMAIN=demo.labclaw.io bash deploy/deploy.sh
set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
REMOTE="${LABCLAW_REMOTE:?Set LABCLAW_REMOTE to SSH host (e.g. export LABCLAW_REMOTE=my-server)}"
REMOTE_DIR="/opt/labclaw"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_IP=$(ssh "$REMOTE" 'hostname -I | awk "{print \$1}"')

echo "╔══════════════════════════════════════════════════╗"
echo "║  LabClaw Deployment                              ║"
echo "║  Target: ${REMOTE} (${REMOTE_DIR})               ║"
echo "╚══════════════════════════════════════════════════╝"

# ── Step 1: Create remote directories ───────────────────────────────────────
echo "[1/6] Creating remote directories..."
ssh "$REMOTE" "mkdir -p ${REMOTE_DIR}/{data,memory,logs}"
ssh "$REMOTE" "id labclaw &>/dev/null || useradd -r -s /usr/sbin/nologin --no-create-home -d /opt/labclaw labclaw"
ssh "$REMOTE" "chown -R labclaw:labclaw /opt/labclaw"

# ── Step 2: Sync code ──────────────────────────────────────────────────────
echo "[2/6] Syncing code to remote..."
rsync -az --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude '.ruff_cache' \
    --exclude '.mypy_cache' \
    --exclude '.pytest_cache' \
    --exclude 'node_modules' \
    --exclude '.venv' \
    --exclude 'venv' \
    --exclude '*.egg-info' \
    --exclude 'tests/' \
    --exclude 'docs/' \
    --exclude 'deploy/' \
    --exclude '.mcp.json' \
    --exclude '/data/' \
    --exclude '/memory/' \
    --exclude '/logs/' \
    "${LOCAL_DIR}/" "${REMOTE}:${REMOTE_DIR}/"

# Also sync the service file
scp "${LOCAL_DIR}/deploy/labclaw.service" "${REMOTE}:/etc/systemd/system/labclaw.service"

# ── Step 3: Set up Python venv + install deps ──────────────────────────────
echo "[3/6] Setting up Python environment..."
ssh "$REMOTE" bash -s <<'SETUP'
set -euo pipefail
cd /opt/labclaw

# Create venv if missing
if [ ! -d venv ]; then
    python3 -m venv venv
    echo "Created venv"
fi

# Upgrade pip
venv/bin/pip install --upgrade pip -q

# Install the package in editable mode
venv/bin/pip install -e ".[science]" -q 2>&1 | tail -5
echo "Dependencies installed"
SETUP

# ── Step 4: Create demo data ──────────────────────────────────────────────
echo "[4/6] Creating demo data..."
ssh "$REMOTE" bash -s <<'DEMO'
set -euo pipefail
cd /opt/labclaw

# Generate a sample CSV if data dir is empty
if [ -z "$(ls -A data/ 2>/dev/null)" ]; then
    venv/bin/python -c "
import csv, random, pathlib

rng = random.Random(42)
data_dir = pathlib.Path('data')

# Behavioral session data with 3 hidden clusters
with (data_dir / 'behavioral_sessions.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['session_id', 'timestamp', 'firing_rate', 'speed', 'accuracy', 'trial_type', 'duration'])
    for i in range(50):
        cluster = i % 3
        base_rate = [10, 25, 40][cluster]
        base_speed = [30, 15, 5][cluster]
        writer.writerow([
            f's{i:03d}',
            i * 3600,
            round(base_rate + rng.gauss(0, 2), 2),
            round(base_speed + rng.gauss(0, 3), 2),
            round(0.6 + cluster * 0.15 + rng.gauss(0, 0.05), 3),
            ['baseline', 'stim', 'recovery'][cluster],
            round(120 + rng.gauss(0, 20), 1),
        ])

# Time-series data with a trend
with (data_dir / 'daily_metrics.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['session_id', 'day', 'performance', 'weight', 'response_time'])
    for i in range(30):
        writer.writerow([
            f'd{i:03d}',
            i,
            round(0.5 + i * 0.01 + rng.gauss(0, 0.03), 3),
            round(25 + rng.gauss(0, 0.5), 1),
            round(200 - i * 2 + rng.gauss(0, 10), 1),
        ])

print(f'Created demo data: {list(data_dir.glob(\"*.csv\"))}')
"
    echo "Demo data created"
else
    echo "Data directory not empty, skipping demo data"
fi
DEMO

# ── Step 5: Create SOUL.md for labclaw entity ─────────────────────────────
echo "[5/6] Initializing memory..."
ssh "$REMOTE" bash -s <<'MEMORY'
set -euo pipefail
mkdir -p /opt/labclaw/memory/labclaw

if [ ! -f /opt/labclaw/memory/labclaw/SOUL.md ]; then
cat > /opt/labclaw/memory/labclaw/SOUL.md <<'EOF'
---
name: LabClaw
type: system
version: 0.0.1
created: 2026-02-20
---

# LabClaw

Self-evolving agentic lab intelligence daemon.

## Purpose

24/7 monitoring, pattern discovery, hypothesis generation, and
self-evolution for neuroscience laboratory data.

## Capabilities

- Edge file watching (new data detection)
- Pattern mining (trends, anomalies, correlations)
- Hypothesis generation
- Predictive modeling
- Self-evolution (analysis parameter optimization)
- Persistent memory (Tier A markdown + Tier B knowledge graph)
EOF
echo "SOUL.md created"
fi

if [ ! -f /opt/labclaw/memory/labclaw/MEMORY.md ]; then
cat > /opt/labclaw/memory/labclaw/MEMORY.md <<'EOF'
---
entity_id: labclaw
type: system_log
---

# LabClaw Memory

EOF
echo "MEMORY.md created"
fi
MEMORY

# ── Step 6: Enable and start service ──────────────────────────────────────
echo "[6/6] Starting LabClaw service..."
ssh "$REMOTE" bash -s <<'START'
set -euo pipefail
systemctl daemon-reload
systemctl enable labclaw
systemctl restart labclaw
sleep 3
systemctl status labclaw --no-pager | head -15
echo ""
echo "API:       http://localhost:18800/api/health"
echo "Dashboard: http://localhost:18801"
START

# ── Step 7 (optional): Set up Caddy reverse proxy ─────────────────────────
if [ -n "${LABCLAW_DOMAIN:-}" ]; then
    echo "[7/7] Setting up Caddy reverse proxy for ${LABCLAW_DOMAIN}..."

    # Upload Caddyfile with domain substituted
    ssh "$REMOTE" "mkdir -p /etc/caddy"
    sed "s/{\$LABCLAW_DOMAIN}/${LABCLAW_DOMAIN}/g" \
        "${LOCAL_DIR}/deploy/Caddyfile" | ssh "$REMOTE" "cat > /etc/caddy/Caddyfile"

    ssh "$REMOTE" bash -s <<'CADDY'
set -euo pipefail

# Install Caddy if not present
if ! command -v caddy &>/dev/null; then
    apt-get update -q
    apt-get install -y -q debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -q
    apt-get install -y -q caddy
    echo "Caddy installed"
else
    echo "Caddy already installed: $(caddy version)"
fi

# Allow HTTP/HTTPS through firewall
if command -v ufw &>/dev/null; then
    ufw allow 80/tcp
    ufw allow 443/tcp
    echo "Firewall: opened ports 80 and 443"
fi

# Enable and (re)start Caddy
systemctl daemon-reload
systemctl enable caddy
systemctl restart caddy
sleep 2
systemctl status caddy --no-pager | head -10
CADDY

    echo ""
    echo "  Caddy is running. TLS will be provisioned automatically."
    echo "  API:       https://${LABCLAW_DOMAIN}/api/health"
    echo "  Dashboard: https://${LABCLAW_DOMAIN}"
else
    echo "[7/7] LABCLAW_DOMAIN not set — skipping Caddy setup."
    echo "  To enable TLS: re-run with LABCLAW_DOMAIN=your.domain.com"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  LabClaw deployed successfully!                  ║"
echo "║                                                  ║"
echo "║  API:       http://${REMOTE_IP}:18800/api/health  ║"
echo "║  Dashboard: http://${REMOTE_IP}:18801             ║"
echo "║                                                  ║"
echo "║  Logs: ssh ${REMOTE} journalctl -u labclaw -f     ║"
echo "║  Status: ssh ${REMOTE} systemctl status labclaw  ║"
echo "╚══════════════════════════════════════════════════╝"
