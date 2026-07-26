# 🚀 GCP Virtual Machine Deployment & Architecture Guide

This guide details the complete, production-tested workflow for packaging, deploying, and maintaining the **Dailsmart AI / Dograh Voice AI Platform** on a **Google Cloud Platform (GCP) Compute Engine Virtual Machine** using Docker Compose.

---

## 📋 Table of Contents
- [1. Overview & Architecture](#1-overview--architecture)
- [2. Prerequisites](#2-prerequisites)
- [3. Deployment Steps](#3-deployment-steps)
  - [Step 1: Create local code archive (`tar.gz`)](#step-1-create-local-code-archive-targz)
  - [Step 2: Upload archive to GCP VM](#step-2-upload-archive-to-gcp-vm)
  - [Step 3: Remote build and container lifecycle](#step-3-remote-build-and-container-lifecycle)
  - [Step 4: Database init & migrations](#step-4-database-init--migrations)
- [4. Automated Deployment Scripts](#4-automated-deployment-scripts)
- [5. Server Maintenance & Disk Cleanup](#5-server-maintenance--disk-cleanup)
- [6. SSL & NGINX Reverse Proxy Setup](#6-ssl--nginx-reverse-proxy-setup)
- [7. Operational & Verification Commands](#7-operational--verification-commands)

---

## 1. Overview & Architecture

The application runs as a multi-container stack orchestrated via Docker Compose under the `remote` profile:

```
[ Client Browser / WebRTC ] ──(HTTPS: 443 / WSS)──> [ NGINX Reverse Proxy ]
                                                         │
                        ┌────────────────────────────────┴──────────────────────────────┐
                        │                                                               │
                [ Next.js UI (Port 3010) ]                            [ FastAPI Backend (Port 8000) ]
                        │                                                               │
            ┌───────────┴─────────────┬───────────────────────────┬─────────────────────┴───────────┐
            │                         │                           │                                 │
     [ PostgreSQL 17 ]          [ Redis 7 ]             [ MinIO S3 Audio Storage ]      [ Asterisk Gateway ]
```

---

## 2. Prerequisites

1. **Local Environment**:
   - Python 3.10+
   - Google Cloud SDK (`gcloud` CLI logged into GCP)
   - Git repository workspace
2. **GCP Virtual Machine**:
   - Ubuntu / Debian VM instance (e.g. `dograh-server-us` in `us-central1-a`)
   - Docker & Docker Compose installed
   - External IP and SSL wildcard hostname (e.g. `*.sslip.io` or custom domain)

---

## 3. Deployment Steps

### Step 1: Create local code archive (`tar.gz`)

Run `scripts/tar_deploy.py` locally to build a clean tarball (`deploy_code.tar.gz`) excluding unneeded directories (`node_modules`, `.next`, `venv`, `.git`, `.venv`):

```bash
python scripts/tar_deploy.py
```

### Step 2: Upload archive to GCP VM

Transfer the compressed archive to your GCP Compute Engine VM using `gcloud compute scp`:

```bash
gcloud compute scp deploy_code.tar.gz dograh-server-us:/home/palav/deploy_code.tar.gz --zone=us-central1-a
```

### Step 3: Remote build and container lifecycle

Extract the archive and trigger a clean Docker Compose rebuild on the VM:

```bash
gcloud compute ssh dograh-server-us --zone=us-central1-a --command="
  tar -xzf /home/palav/deploy_code.tar.gz -C /home/palav/dograh/ && \
  cd /home/palav/dograh && \
  REGISTRY=local docker compose --profile remote build api ui && \
  REGISTRY=local docker compose --profile remote down && \
  REGISTRY=local docker compose --profile remote up -d
"
```

### Step 4: Database init & migrations

The `dograh_init` service automatically applies database migrations and seeds initial required schemas on startup:

```bash
gcloud compute ssh dograh-server-us --zone=us-central1-a --command="
  cd /home/palav/dograh && \
  sudo REGISTRY=local docker compose run --rm dograh_init
"
```

---

## 4. Automated Deployment Scripts

Two helper scripts in `scripts/` automate the packaging and remote deployment:

1. **`scripts/tar_deploy.py`**:
   - Collects all source code, `api/`, `ui/`, `docker-compose.yaml`, and dependencies.
   - Ignores heavy build artifacts (`node_modules`, `.next`, `.venv`).
   - Produces `deploy_code.tar.gz` (~9.5 MB).

2. **`scripts/upload_and_build.py`**:
   - Uploads `deploy_code.tar.gz` directly to GCP VM via `gcloud scp`.
   - Executes remote extraction and runs `docker compose --profile remote up -d --build`.

```bash
# Full automated one-command deploy:
python scripts/tar_deploy.py && python scripts/upload_and_build.py
```

---

## 5. Server Maintenance & Disk Cleanup

To prevent disk fill issues (`ENOSPC: no space left on device`) from accumulated Docker build layers:

```bash
# Reclaim disk space by clearing unused containers, networks, and build cache
gcloud compute ssh dograh-server-us --zone=us-central1-a --command="
  sudo docker system prune -af --volumes && df -h /
"
```

---

## 6. SSL & NGINX Reverse Proxy Setup

1. **NGINX Container (`nginx_https`)**:
   - Proxies incoming HTTPS traffic on Port 443 to `dograh-ui-1:3010` and `/api/v1` to `dograh-api-1:8000`.
2. **SSL Certificates**:
   - Stored under `/home/palav/dograh/infrastructure/nginx/certs/`.

---

## 7. Operational & Verification Commands

```bash
# Check container status
gcloud compute ssh dograh-server-us --zone=us-central1-a --command="sudo docker ps"

# Check API health endpoint
curl -k https://136.119.37.251.sslip.io/api/v1/health

# View live API logs
gcloud compute ssh dograh-server-us --zone=us-central1-a --command="sudo docker logs -f --tail=100 dograh-api-1"

# View live UI logs
gcloud compute ssh dograh-server-us --zone=us-central1-a --command="sudo docker logs -f --tail=100 dograh-ui-1"
```
