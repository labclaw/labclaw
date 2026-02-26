# Deployment Guide

---

## Docker (Single Container)

### Build

```bash
docker build -t labclaw .
```

### Run

```bash
docker run -d \
  --name labclaw \
  -p 18800:18800 \
  -p 18801:18801 \
  -v /opt/labclaw/data:/data \
  -v /opt/labclaw/memory:/memory \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  labclaw \
  --data-dir /data --memory-root /memory
```

### Health Check

The image includes a built-in health check that polls `/health` every 30 seconds.

```bash
docker inspect --format='{{.State.Health.Status}}' labclaw
```

---

## Docker Compose (with Redis)

For multi-node deployments or when you want persistent event streaming, use Redis
as the event backend.

Create `docker-compose.yml`:

```yaml
version: "3.9"

services:
  labclaw:
    build: .
    ports:
      - "18800:18800"
      - "18801:18801"
    volumes:
      - labclaw-data:/data
      - labclaw-memory:/memory
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    command: ["--data-dir", "/data", "--memory-root", "/memory"]
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped

volumes:
  labclaw-data:
  labclaw-memory:
  redis-data:
```

Update `configs/default.yaml` to use Redis:

```yaml
events:
  backend: redis
  redis_url: redis://redis:6379
```

Start:

```bash
docker compose up -d
```

---

## Systemd Service

For bare-metal deployments on Linux servers.

### 1. Create Service File

Save as `/etc/systemd/system/labclaw.service`:

```ini
[Unit]
Description=LabClaw Lab Intelligence Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=labclaw
Group=labclaw
WorkingDirectory=/opt/labclaw
ExecStart=/opt/labclaw/venv/bin/labclaw serve \
    --data-dir /opt/labclaw/data \
    --memory-root /opt/labclaw/memory \
    --host 0.0.0.0 \
    --port 18800 \
    --dashboard-host 0.0.0.0 \
    --dashboard-port 18801
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment=ANTHROPIC_API_KEY=sk-ant-...

[Install]
WantedBy=multi-user.target
```

### 2. Create System User

```bash
sudo useradd -r -s /usr/sbin/nologin --no-create-home -d /opt/labclaw labclaw
sudo mkdir -p /opt/labclaw/{data,memory,logs}
sudo chown -R labclaw:labclaw /opt/labclaw
```

### 3. Install and Enable

```bash
cd /opt/labclaw
python3 -m venv venv
venv/bin/pip install "labclaw[science]"

sudo systemctl daemon-reload
sudo systemctl enable labclaw
sudo systemctl start labclaw
```

### 4. Monitor

```bash
sudo systemctl status labclaw
sudo journalctl -u labclaw -f
```

---

## Automated Deployment Script

LabClaw includes `deploy/deploy.sh` for deploying to a remote server via SSH.

### Prerequisites

- SSH access configured (e.g. via `~/.ssh/config` alias `claw`)
- Python 3.11+ on the remote server
- rsync installed

### Usage

```bash
bash deploy/deploy.sh
```

The script:

1. Creates remote directories (`/opt/labclaw/{data,memory,logs}`).
2. Syncs code via rsync (excludes tests, docs, caches).
3. Creates/updates Python venv and installs dependencies.
4. Generates demo data if data directory is empty.
5. Initializes SOUL.md and MEMORY.md for the system entity.
6. Installs and starts the systemd service.

Customize the target via environment variables:

```bash
# Required: SSH host alias or user@host
export LABCLAW_REMOTE=my-server

# Optional: domain for automatic TLS (Caddy)
export LABCLAW_DOMAIN=demo.labclaw.io

bash deploy/deploy.sh
```

---

## Caddy Reverse Proxy (Automatic TLS)

LabClaw services bind to `127.0.0.1` by default. Use Caddy as a reverse proxy to expose
them over HTTPS with automatic certificate provisioning via Let's Encrypt.

### Prerequisites

- A domain name with an A record pointing to the server IP.
- Ports 80 and 443 reachable from the internet (required by Let's Encrypt HTTP challenge).
- The `LABCLAW_REMOTE` SSH alias configured.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LABCLAW_REMOTE` | Yes | SSH host (alias or `user@host`) |
| `LABCLAW_DOMAIN` | No | Domain for TLS — if set, Caddy is installed and configured |

### Automatic Setup via Deploy Script

Set `LABCLAW_DOMAIN` before running `deploy.sh` and Caddy is installed automatically:

```bash
export LABCLAW_REMOTE=my-server
export LABCLAW_DOMAIN=demo.labclaw.io
bash deploy/deploy.sh
```

The script:

1. Installs Caddy from the official Cloudsmith apt repository.
2. Writes `/etc/caddy/Caddyfile` with routes for `/api/*` and `/*`.
3. Opens ports 80 and 443 in `ufw`.
4. Enables and starts the `caddy` systemd service.

### Manual Setup

Install Caddy on the server, copy the Caddyfile, and start the service:

```bash
# Upload and apply the Caddyfile
scp deploy/Caddyfile my-server:/etc/caddy/Caddyfile
ssh my-server "systemctl restart caddy"
```

### Caddyfile Reference

The `deploy/Caddyfile` uses `{$LABCLAW_DOMAIN}` as a placeholder. When deploying
manually, replace it with your domain or export the variable before starting Caddy:

```bash
export LABCLAW_DOMAIN=demo.labclaw.io
caddy run --config /etc/caddy/Caddyfile
```

Routing rules:

| Path | Upstream | Notes |
|------|----------|-------|
| `/api/*` | `localhost:18800` | FastAPI REST API |
| `/*` | `localhost:18801` | Streamlit dashboard |

Security headers set by Caddy on every response:

| Header | Value |
|--------|-------|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Server` | (removed) |

### Verify TLS

After deployment, confirm the certificate is active:

```bash
curl -I https://demo.labclaw.io/api/health
# Expect: HTTP/2 200
```

Check Caddy logs for certificate issuance:

```bash
ssh my-server "journalctl -u caddy -f"
```

Caddy renews certificates automatically before expiry — no cron job needed.

---

## Cloud Deployment

### DigitalOcean

1. Create a Droplet (Ubuntu 22.04+, 2GB+ RAM).
2. SSH in and install Python:

```bash
apt update && apt install -y python3.11 python3.11-venv
```

3. Use the deploy script or install manually:

```bash
mkdir -p /opt/labclaw && cd /opt/labclaw
python3.11 -m venv venv
venv/bin/pip install "labclaw[science]"
```

4. Set up the systemd service (see above).

5. Open firewall ports:

```bash
ufw allow 18800/tcp   # API
ufw allow 18801/tcp   # Dashboard
```

If you want local-only access (for SSH tunnel or reverse proxy setup), use:

```ini
--host 127.0.0.1 --dashboard-host 127.0.0.1
```

### AWS EC2

1. Launch an EC2 instance (t3.small or larger, Ubuntu AMI).
2. Configure Security Group to allow ports 18800 and 18801.
3. Install and configure as above.

For persistent storage, attach an EBS volume and mount it at `/opt/labclaw/data`.

### GCP Compute Engine

1. Create a VM instance (e2-small or larger).
2. Configure firewall rules for ports 18800-18801.
3. Install and configure as above.

---

## Configuration for Production

### API Keys

Never hardcode API keys. Use environment variables:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

For systemd, add to the service file:

```ini
Environment=ANTHROPIC_API_KEY=sk-ant-...
```

For Docker, use a `.env` file:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
docker compose --env-file .env up -d
```

### Data Directories

| Directory | Purpose | Recommended path |
|-----------|---------|-----------------|
| Data dir | Watched for new files | `/opt/labclaw/data` |
| Memory root | Tier A markdown memory | `/opt/labclaw/memory` |
| Logs | Dashboard and system logs | `/opt/labclaw/logs` |

### Ports

| Service | Default port | Flag |
|---------|-------------|------|
| REST API | 18800 | `--port` |
| Dashboard | 18801 | `--dashboard-port` |

### Bind Addresses

| Service | Default host | Flag |
|---------|--------------|------|
| REST API | `127.0.0.1` | `--host` |
| Dashboard | `127.0.0.1` | `--dashboard-host` |

### Intervals

| Interval | Default | Flag |
|----------|---------|------|
| Discovery | 300s (5 min) | `--discovery-interval` |
| Evolution | 1800s (30 min) | `--evolution-interval` |

For production, increase the discovery interval to reduce load:

```bash
labclaw serve --discovery-interval 600 --evolution-interval 3600
```

---

## Backup and Recovery

### What to Back Up

| Item | Path | How |
|------|------|-----|
| Tier A memory | `/opt/labclaw/memory/` | `rsync` or git |
| SQLite database | `/opt/labclaw/data/labclaw.db` | `sqlite3 .backup` |
| Evolution state | `/opt/labclaw/memory/evolution_state.json` | File copy |
| Audit log | `/opt/labclaw/logs/audit.jsonl` | File copy |
| Configuration | `/opt/labclaw/configs/` | Version control |

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/backup/labclaw/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Tier A memory (git-tracked markdown)
rsync -a /opt/labclaw/memory/ "$BACKUP_DIR/memory/"

# SQLite database
sqlite3 /opt/labclaw/data/labclaw.db ".backup '$BACKUP_DIR/labclaw.db'"

# Evolution state
cp /opt/labclaw/memory/evolution_state.json "$BACKUP_DIR/"

# Config
cp -r /opt/labclaw/configs/ "$BACKUP_DIR/configs/"

echo "Backup complete: $BACKUP_DIR"
```

### Recovery

1. Stop the service: `systemctl stop labclaw`
2. Restore files from backup.
3. Start the service: `systemctl start labclaw`

Evolution state and Tier A memory are automatically loaded on startup.

---

## Monitoring and Alerting

### Health Check Script

```bash
#!/bin/bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:18800/api/health)
if [ "$STATUS" != "200" ]; then
    echo "LabClaw health check failed (HTTP $STATUS)" | \
        mail -s "LabClaw Alert" admin@lab.edu
fi
```

### Cron Monitoring

```bash
# Check every 5 minutes
*/5 * * * * /opt/labclaw/scripts/healthcheck.sh
```

### Log Monitoring

```bash
# Follow logs
journalctl -u labclaw -f

# Search for errors
journalctl -u labclaw --since "1 hour ago" | grep -i error
```
