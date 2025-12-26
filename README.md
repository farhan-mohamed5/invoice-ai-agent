# Invoice AI Agent (UAE-focused) — Monorepo

AI-powered invoice/receipt filing system built for **UAE business expenses**: ingest invoices (upload, inbox folder, or email), extract key fields using **OCR + a local LLM (Ollama)**, apply vendor/category rules, and resolve uncertain extractions through a fast **AI review workflow** in the web UI.

> Best on **macOS/Linux** (local Ollama + Python + Node).  
> **Windows supported** (PowerShell + Python + Node; Ollama works on Windows too).

---

## Demo - Videos

### File Upload via Web Interface
[![File Upload via Web Interface](https://img.youtube.com/vi/93WGCsHu1AY/hqdefault.jpg)](https://youtu.be/93WGCsHu1AY)

### Email Upload
[![Email Upload](https://img.youtube.com/vi/fWXpwIxhqq0/hqdefault.jpg)](https://youtu.be/fWXpwIxhqq0)

### Invoice with Missing Details (Review Flow)
[![Invoice with Missing Details](https://img.youtube.com/vi/f9TtWynpCiU/hqdefault.jpg)](https://youtu.be/f9TtWynpCiU)

## Demo - UI Screenshots
<img width="1440" height="784" alt="SCR-20251226-fkuq" src="https://github.com/user-attachments/assets/9d1193d4-4e84-4de3-b4d8-2f145c6e3ecd" />
<img width="1440" height="788" alt="SCR-20251226-flao" src="https://github.com/user-attachments/assets/d7a80512-737b-43ac-a47c-035c64e70b0e" />
<img width="1440" height="785" alt="SCR-20251226-flix" src="https://github.com/user-attachments/assets/7ee83ffe-d445-4f8b-ad03-14e38648052a" />
<img width="1440" height="786" alt="SCR-20251226-ggdn" src="https://github.com/user-attachments/assets/40c39ee8-4fb6-4ad9-a790-2dbf1ae0c5e5" />


```md
![Dashboard](docs/screenshots/dashboard.png)
```

---

## Table of contents

1. [Architecture](#architecture)  
2. [Project structure](#project-structure)  
3. [Features](#features)  
4. [Requirements](#requirements)  
5. [Quick start](#quick-start)  
6. [Configuration](#configuration)  
7. [Run the services](#run-the-services)  
8. [Email automation](#email-automation)  
9. [Database migrations (Alembic)](#database-migrations-alembic)  
10. [VAT handling](#vat-handling)  
11. [Analytics dashboard](#analytics-dashboard)  
12. [Troubleshooting](#troubleshooting)  
13. [Security & safe sharing](#security--safe-sharing)  
14. [License](#license)

---

## Architecture

This repository is a **monorepo**:

- **Backend API (FastAPI):** `apps/api/`  
  Upload endpoints, invoice CRUD, status updates, review resolution, and dashboard data.
- **Worker pipeline:** `apps/worker/`  
  Watches an inbox folder, runs OCR/LLM extraction, normalizes vendor/category, stores results, and organizes files.
- **Frontend (Next.js):** `apps/frontend/`  
  Dashboard + invoices table + invoice detail + review UI.
- **Background tasks (Celery + Redis):** used for long-running work (OCR/LLM/processing) without blocking the API.

### High-level flow

1. Invoice arrives via **upload / inbox folder / email ingest**
2. Text extracted (**PDF text** or **OCR**)
3. LLM returns structured fields (with confidence signals)
4. Vendor/category rules normalize and validate fields
5. If something is missing → invoice becomes `needs_review` with targeted questions
6. User resolves → invoice becomes `ok` and updates persist

---

## Project structure

> If your repo differs slightly, this is the intended shape.

```text
invoice_agent/
├─ apps/
│  ├─ api/                      # FastAPI backend
│  ├─ worker/                   # watcher + pipeline + background jobs
│  └─ frontend/                 # Next.js UI
├─ invoice_agent_data/          # local data (NOT committed)
│  ├─ Invoices_Inbox/           # drop PDFs/images/email-body txt here
│  ├─ Invoices/                 # organized processed files
│  ├─ logs/                     # worker/email/celery logs
│  └─ invoices.db               # local DB (or whatever your DB path is)
├─ docs/
│  └─ screenshots/
├─ .env                         # local env vars (NOT committed)
├─ .env.example                 # safe placeholders (committed)
├─ requirements.txt             # python deps (recommended)
└─ README.md
```

### Data directory (invoice_agent_data)

Recommended local layout:

- `invoice_agent_data/Invoices_Inbox/`  
  Raw incoming invoices (from upload/email/watcher).
- `invoice_agent_data/Invoices/`  
  Organized output (by vendor/date/status — your pipeline decides).
- `invoice_agent_data/invoices.db`  
  Local database file (if using SQLite).
- `invoice_agent_data/logs/`  
  Logs for watcher/email/celery.

---

## Features

### 1) Multi-source ingest
- **Upload via web UI** for manual imports
- **Inbox folder watcher** for “drop files and forget” workflows
- **Email ingest (IMAP)** fetches unseen messages and saves invoice-like attachments/body into the inbox so the watcher can process them automatically

**Supported inputs**
- PDFs (most common)
- Images (JPG/PNG) for scanned invoices/receipts
- Email-body `.txt` imports (for invoices that are text-only in the email)

---

### 2) OCR + parsing (PDF + images)
- PDF text extraction for digital invoices
- OCR fallback for scanned docs/images
- Handles common invoice formats: receipts, utility bills, subscription invoices, transport/toll receipts

---

### 3) LLM structured extraction (local Ollama)
Uses a local model (Ollama) to extract a consistent schema, typically:
- `date`
- `vendor`
- `amount`
- `currency`
- `tax_amount` / VAT (when present)
- `category`
- `is_paid` / status (when inferable)
- `notes` and ambiguity signals

If Ollama is unavailable, extraction falls back to a minimal scaffold and invoices are more likely to be flagged for review.

---

### 4) Review workflow (fast fixing)
- If critical fields are missing or confidence is low, invoices are flagged `needs_review`
- The UI displays **targeted questions** (kept short) to fix missing/uncertain fields quickly
- On submit, the invoice is updated and marked `ok`

This keeps the system practical: it’s fast when extraction is good, and still usable when it isn’t.

---

### 5) Web UI
- Invoices table with:
  - Search and filters (status/payment/category/vendor/date range)
  - Sorting + pagination
  - Quick actions (e.g., Paid / Not Paid)
- Invoice detail page with:
  - extracted fields + source file preview
  - review questions + resolution

---

### 6) Background processing (Celery + Redis)
Long-running tasks (OCR, LLM extraction, PDF-to-image conversion) can run in the background:
- API stays responsive
- retries for transient failures
- ability to monitor/clear stuck jobs

---

## Requirements

### System
- **Python 3.11+**
- **Node.js 18+** (20 recommended)
- **Ollama installed + running**
- **Redis** (for Celery broker)
- **Tesseract OCR** (recommended for image-heavy receipts)

### Ollama (required)

macOS/Linux:
```bash
ollama pull llama3
```

Windows (PowerShell):
```powershell
ollama pull llama3
```

### Recommended `requirements.txt` (baseline)

> If your repo doesn’t ship with a requirements file yet, you can start from this and tighten it later.

```txt
fastapi
uvicorn[standard]
python-dotenv
python-multipart

sqlalchemy
alembic

requests
httpx

pdfplumber
pillow
pytesseract
pdf2image

celery
redis

# If your code calls Ollama via a Python client (optional; install only if used)
ollama
```

---

## Quick start

### 1) Clone
```bash
git clone <YOUR_REPO_URL>
cd invoice_agent
```

### 2) Create & activate venv

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
```

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip setuptools wheel
```

### 3) Install Python dependencies

If you have `requirements.txt`:
```bash
python -m pip install -r requirements.txt
```

If you don’t yet, install the baseline set (then freeze later):
```bash
python -m pip install fastapi "uvicorn[standard]" python-dotenv python-multipart \
  sqlalchemy alembic requests httpx \
  pdfplumber pillow pytesseract pdf2image \
  celery redis
```

Optional (if your code imports a Python Ollama client):
```bash
python -m pip install ollama
```

### 4) Install frontend dependencies
```bash
cd apps/frontend
npm install
```

### 5) Create local data folders
```bash
mkdir -p invoice_agent_data/Invoices_Inbox
mkdir -p invoice_agent_data/Invoices
mkdir -p invoice_agent_data/logs
```

---

## Configuration

### Frontend: `apps/frontend/.env.local`
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

### Backend/Worker: repo root `.env`
```env
# LLM (Ollama)
INVOICE_AGENT_ENABLE_LLM=1
INVOICE_AGENT_LLM_MODEL=llama3
INVOICE_AGENT_LLM_TEMP=0.1

# Local data paths
INVOICE_AGENT_DATA_DIR=./invoice_agent_data
INVOICE_AGENT_INBOX=./invoice_agent_data/Invoices_Inbox
INVOICE_AGENT_OUTPUT=./invoice_agent_data/Invoices
INVOICE_AGENT_DB_PATH=./invoice_agent_data/invoices.db

# Celery / Redis (broker)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email ingest (IMAP) — only if using email ingest
RECEIPT_AGENT_IMAP_HOST=imap.gmail.com
RECEIPT_AGENT_IMAP_USER=your_email@gmail.com
RECEIPT_AGENT_IMAP_PASSWORD=your_app_password
RECEIPT_AGENT_IMAP_FOLDER=INBOX
```

> If your code doesn’t auto-load `.env`, export variables in the same terminal session before running.

---

## Run the services

You will typically use **3 terminals**, and **a 4th** if background processing is enabled.

### Terminal A — Backend API (FastAPI)
```bash
cd /path/to/invoice_agent
source .venv/bin/activate  # macOS/Linux
export PYTHONPATH="$PWD"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal B — Frontend (Next.js)
```bash
cd /path/to/invoice_agent/apps/frontend
npm run dev
```

### Terminal C — Worker / watcher (folder ingest)
```bash
cd /path/to/invoice_agent
source .venv/bin/activate  # macOS/Linux
python apps/worker/pipeline/watcher_cli.py
```

### Terminal D — Background worker (Celery)
1) Start Redis (choose one option):

**Option A: Docker**
```bash
docker run --name invoice-agent-redis -p 6379:6379 -d redis:7
```

**Option B: macOS (Homebrew)**
```bash
brew install redis
brew services start redis
```

2) Start Celery worker

Because repos differ on where the Celery app is defined, first locate it:
```bash
python -c "import glob; print('\n'.join([p for p in glob.glob('**/*.py', recursive=True) if 'celery' in p.lower()]))"
```

Then search for the Celery app definition:
```bash
grep -R "Celery(" -n apps | head -n 20
```

Once you identify the module that exposes `celery_app` (example path shown below), run:
```bash
celery -A apps.worker.pipeline.celery_app:celery_app worker -l info
```

If your app uses a different name (e.g., `app`), adjust accordingly:
```bash
celery -A <your.module.path>:<your_celery_instance> worker -l info
```

Open:
- Frontend: `http://localhost:3000`
- API: `http://127.0.0.1:8000`

---

## Email automation

### Run email ingest manually
```bash
cd /path/to/invoice_agent
source .venv/bin/activate
python apps/worker/pipeline/email_ingest_imap.py
```

### Run periodically (cron)
Example: every 5 minutes:
```bash
crontab -e
```

Add:
```cron
*/5 * * * * cd /path/to/invoice_agent && . .venv/bin/activate && python apps/worker/pipeline/email_ingest_imap.py >> invoice_agent_data/logs/imap.log 2>&1
```

---

## Database migrations (Alembic)

If you’re using SQLAlchemy models, Alembic keeps schema changes clean and repeatable.

### One-time setup
From repo root:
```bash
source .venv/bin/activate
alembic init alembic
```

Then:
- set your DB URL in `alembic.ini` (or wire it via env var)
- point Alembic `env.py` to your SQLAlchemy `Base.metadata`

### Create a migration
```bash
alembic revision --autogenerate -m "create invoices table"
```

### Apply migrations
```bash
alembic upgrade head
```

### Downgrade (if needed)
```bash
alembic downgrade -1
```

---

## VAT handling

### Current gap
VAT handling needs to be consistent and automatic.

### Target behavior (UAE 5%)
- If invoice clearly shows VAT, store it in `tax_amount` and keep totals consistent.
- If VAT is missing but the amount looks like **net** (no VAT mentioned), auto-calculate:
  - `vat = round(net_amount * 0.05, 2)`
  - `gross = net_amount + vat`
- If the invoice amount looks **VAT-inclusive**, either:
  - store `gross_amount` and derive `vat_component` (when you have enough signals), or
  - mark for review with a question like: “Is this amount VAT-inclusive?”

Recommended: keep an explicit flag like `vat_inclusive` to avoid guesswork.

---

## Analytics dashboard

### Planned / upcoming (not finished)
- **Recurring expenses detection (AI):**
  - detect repeated vendors + similar amounts (monthly subscriptions, utilities)
  - highlight “likely recurring” vs “one-off”
- **VAT insights:**
  - VAT totals by month/vendor/category
  - VAT-heavy categories and trends
- **Spending trends:**
  - monthly burn
  - category breakdown
  - top vendors
  - paid vs unpaid trends
- **Anomalies:**
  - unusually high invoices vs baseline
  - sudden vendor spikes

---

## Troubleshooting

### `pip: bad interpreter ...`
Your venv was created from a moved/old path. Rebuild it:
```bash
deactivate 2>/dev/null || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

### `ModuleNotFoundError: <package>`
Install the missing module:
```bash
python -m pip install <package>
```

### Celery / Redis issues

**Redis connection refused**
- Check Redis is running:
```bash
redis-cli ping
```
Expected: `PONG`

**Celery worker can’t connect to broker**
- Confirm `CELERY_BROKER_URL` matches your Redis URL:
```bash
echo $CELERY_BROKER_URL
```

**Tasks stuck / piling up**
- Restart Redis + Celery worker
- Purge queue (careful: deletes queued jobs):
```bash
celery -A <your.module.path>:<your_celery_instance> purge -f
```

**Worker not executing tasks**
- Ensure your API is actually enqueuing to Celery (not running tasks inline)
- Check worker logs in terminal (or redirect to `invoice_agent_data/logs/celery.log`)

---

## Security & safe sharing

If publishing this repository:
- Never commit `.env`, app passwords, DB files, or real invoices
- Use Gmail **App Passwords** (not your normal password) for IMAP

Recommended `.gitignore` additions:
```gitignore
# env / secrets
.env
.env.*
*.key
*.pem

# python
.venv/
__pycache__/
*.pyc

# node
node_modules/
.next/

# data
*.db
invoice_agent_data/
apps/**/invoice_agent_data/
logs/
```

Add an `.env.example` with placeholders (safe to commit).

---

## License

Pick one:
- MIT
- Proprietary

Add a `LICENSE` file accordingly.
