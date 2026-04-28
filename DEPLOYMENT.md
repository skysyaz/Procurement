# ProcureFlow — Self-Hosted Deployment Guide

This guide assumes you've pushed the code to your GitHub repo and want to run ProcureFlow on an internal server at your office (Linux VM, bare-metal, or NAS).

---

## 1. Minimum requirements

| Component | Minimum | Recommended |
|---|---|---|
| OS | Linux x86_64 (Ubuntu 22.04 / Debian 12 / RHEL 9) | Same |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB SSD | 50 GB SSD (grows with uploaded PDFs) |
| Network | Port 80/443 reachable on LAN | + reverse proxy w/ TLS |

Software baseline installed via `apt`:
- Docker Engine ≥ 24 + Docker Compose plugin
- `git`
- (Optional) Caddy / Nginx / Traefik for TLS termination

---

## 2. Option A — Docker Compose (recommended for on-prem)

Create the following files at the root of your repo (next to `backend/` and `frontend/`).

### 2.1 `backend/Dockerfile`
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr poppler-utils curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir pytesseract pdf2image resend celery redis

COPY backend/ ./
RUN mkdir -p /app/uploads

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

### 2.2 `frontend/Dockerfile`
```dockerfile
# ---- build stage ----
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile
COPY frontend/ ./
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
RUN yarn build

# ---- serve stage ----
FROM nginx:1.27-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 2.3 `frontend/nginx.conf`
```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA routing fallback
    location / {
        try_files $uri /index.html;
    }

    # Proxy /api to the backend container
    location /api/ {
        proxy_pass http://backend:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50m;     # bulk PDF upload ceiling
    }
}
```

### 2.4 `docker-compose.yml`
```yaml
services:
  mongo:
    image: mongo:7
    restart: unless-stopped
    volumes: [mongo_data:/data/db]

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    restart: unless-stopped
    env_file: ./backend/.env.prod
    environment:
      MONGO_URL: mongodb://mongo:27017
      DB_NAME: procureflow
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_BACKEND_URL: redis://redis:6379/1
      USE_CELERY: "true"
    volumes: [uploads:/app/uploads]
    depends_on: [mongo, redis]

  worker:
    build:
      context: .
      dockerfile: backend/Dockerfile
    restart: unless-stopped
    command: celery -A celery_app.celery worker --loglevel=info --concurrency=2
    env_file: ./backend/.env.prod
    environment:
      MONGO_URL: mongodb://mongo:27017
      DB_NAME: procureflow
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_BACKEND_URL: redis://redis:6379/1
    volumes: [uploads:/app/uploads]
    depends_on: [redis, mongo]

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
      args:
        # Use your LAN hostname or domain. For same-origin deploy, keep empty.
        REACT_APP_BACKEND_URL: ""
    restart: unless-stopped
    ports: ["80:80"]
    depends_on: [backend]

volumes:
  mongo_data:
  uploads:
```

### 2.5 `backend/.env.prod` (DO NOT commit — add to `.gitignore`)
```
FRONTEND_URL=http://procureflow.office.local
CORS_ORIGINS=http://procureflow.office.local

# Required — generate with: python3 -c "import secrets;print(secrets.token_hex(32))"
JWT_SECRET=<64-hex-random>

ADMIN_EMAIL=admin@your-company.com
ADMIN_PASSWORD=ChangeMeOnFirstLogin!
ADMIN_NAME=Administrator

# Optional — leave empty to disable email + password reset sends
RESEND_API_KEY=
RESEND_FROM_EMAIL=ProcureFlow <noreply@your-company.com>

# Required for OCR classification + extraction
# At least one of the following must be set:
GEMINI_API_KEY=AIza-xxxxxxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxx
```

### 2.6 Bring it up
```bash
git clone git@github.com:<you>/procureflow.git
cd procureflow
cp backend/.env backend/.env.prod        # then edit
docker compose up -d --build
docker compose logs -f backend           # watch for "Seeded admin user"
```

Open `http://<server-ip>/` → log in with the admin credentials from `.env.prod`.

### 2.7 Upgrade / redeploy
```bash
git pull
docker compose up -d --build
```

### 2.8 Backups
- **Database**: `docker compose exec mongo mongodump --archive=/dump.gz --gzip --db procureflow`
- **Uploaded PDFs**: back up the `uploads` volume (`docker volume inspect procureflow_uploads`).
- A nightly cron that tars both to an NAS is enough for internal use.

---

## 3. Option B — Bare metal / systemd (no Docker)

Use this if IT policy forbids Docker. Tested on Ubuntu 22.04.

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm \
    mongodb redis-server tesseract-ocr poppler-utils nginx

# Backend
cd /opt && sudo git clone https://github.com/<you>/procureflow.git
cd /opt/procureflow/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytesseract pdf2image resend celery redis google-genai
cp .env .env.prod          # edit with values from section 2.5

# Frontend
cd ../frontend
corepack enable
yarn install
REACT_APP_BACKEND_URL="" yarn build       # empty = same-origin; nginx will proxy /api
sudo cp -r build /var/www/procureflow
```

Create three systemd units:

**`/etc/systemd/system/procureflow-api.service`**
```ini
[Unit]
Description=ProcureFlow API
After=network.target mongod.service redis-server.service

[Service]
WorkingDirectory=/opt/procureflow/backend
EnvironmentFile=/opt/procureflow/backend/.env.prod
ExecStart=/opt/procureflow/backend/.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/procureflow-worker.service`**
```ini
[Unit]
Description=ProcureFlow Celery worker
After=network.target redis-server.service

[Service]
WorkingDirectory=/opt/procureflow/backend
EnvironmentFile=/opt/procureflow/backend/.env.prod
ExecStart=/opt/procureflow/backend/.venv/bin/celery -A celery_app.celery worker --loglevel=info --concurrency=2
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

**Nginx site `/etc/nginx/sites-available/procureflow`**
```nginx
server {
    listen 80;
    server_name procureflow.office.local;
    root /var/www/procureflow;
    client_max_body_size 50m;

    location / { try_files $uri /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable & start:
```bash
sudo ln -s /etc/nginx/sites-available/procureflow /etc/nginx/sites-enabled/
sudo systemctl daemon-reload
sudo systemctl enable --now procureflow-api procureflow-worker nginx mongod redis-server
```

---

## 4. Security checklist for internal use

- [ ] `JWT_SECRET` is a fresh 64-hex value (never the one from the preview)
- [ ] `ADMIN_PASSWORD` is changed on first login
- [ ] `FRONTEND_URL` + `CORS_ORIGINS` match your real internal URL
- [ ] Put the service behind HTTPS (Caddy or Nginx + Let's Encrypt DNS-01, or an internal CA)
- [ ] Restrict DNS/firewall so it only resolves on the office LAN or VPN
- [ ] Schedule nightly `mongodump` + `uploads/` tar to an NAS
- [ ] Keep `RESEND_API_KEY` empty until you have a domain + verified sender; the UI shows a 503 with clear instructions when disabled (no crash).

---

## 5. TLS (recommended — takes 2 minutes with Caddy)

Replace nginx with **Caddy** (ships with automatic HTTPS):

```caddy
procureflow.office.local {
    encode gzip zstd
    root * /var/www/procureflow
    try_files {path} /index.html
    file_server
    reverse_proxy /api/* 127.0.0.1:8001
}
```

Caddy auto-provisions certs via your internal ACME server or Let's Encrypt if the hostname is public.

---

## 6. Updating templates / users after deploy

Everything is DB-backed — **you don't redeploy** to change templates or add users:
- Admin → Users → add people / change roles
- Admin → Templates → edit schemas or create new document types
- Admin → Audit Log for compliance

Changing `.env.prod` does require `docker compose restart backend worker` (or `systemctl restart procureflow-api procureflow-worker`) since env is read once at startup.

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| "Seeded admin user" doesn't appear | Check `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env.prod`; restart backend. |
| Bulk upload stuck "PROCESSING" | `docker compose logs worker` — check Celery is connected to Redis. |
| 503 "Configure RESEND_API_KEY" when emailing | Add your Resend API key + verified sender, restart backend. |
| PDF iframe blank on mobile | Expected — mobile Chrome can't render PDF-in-iframe. Tap "Open" card to open PDF in a new tab. |
| CORS errors in browser console | `FRONTEND_URL` in backend `.env.prod` must exactly match the hostname users access. |

---

For questions about the architecture itself, see `/app/memory/PRD.md`.
