# Quickstart & Local Deployment Guide

## Prerequisites

| Tool | Minimum Version |
|---|---|
| Python | 3.11 |
| Node.js | 18.0 |
| pip | 23+ |
| npm | 9+ |

---

## Step 1 — Environment Configuration

Copy the environment template and configure your keys:

```bash
cp .env.example .env
```

Edit `.env`. The critical values:

| Variable | Required? | Description |
|---|---|---|
| `GEMINI_API_KEY` | For live narratives | Your Google Gemini API key |
| `USE_MOCK_C1` | No (default: false) | Set `true` to bypass ml_engine for frontend testing |
| `USE_MOCK_C3` | No (default: false) | Set `true` to bypass c3_engine (uses canned LLM output) |
| `NEXT_PUBLIC_SHOW_SCENARIO_SWITCHER` | No (default: true) | Shows demo scenario switcher widget |

---

## Step 2 — Backend Installation

Install all three Python packages (C1, C2, C3) in one command from the repo root:

```bash
pip install -e backend/
```

This installs `ml_engine`, `c3_engine`, and `api` as editable packages — changes to source files are reflected immediately without reinstalling.

**Verify installation:**
```bash
python -c "import ml_engine, c3_engine, api; print('All packages OK')"
```

---

## Step 3 — Run Backend Tests

```bash
pytest backend/
```

Expected output: all tests in `core/ml_engine/tests/` and `api/api/tests/` passing.

---

## Step 4 — Start Backend API

```bash
cd backend
python -m uvicorn api.api.main:app --reload --port 8000
```

Verify: open http://localhost:8000/health — should return `{"status": "ok"}`.

Interactive API docs: http://localhost:8000/docs

---

## Step 5 — Frontend Setup

In a new terminal:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000.

---

## One-Command Alternative

From the repo root:

```powershell
# Windows
.\start.ps1
```

```bash
# Linux / macOS
./start.sh
```

---

## Demo Flow

1. Open http://localhost:3000.
2. Use the **Scenario Switcher** (bottom-right) to load the **Critical** scenario instantly — no CSV required.
3. Observe: health score, correlated anomaly cards, prescriptions, matched cases, executive narrative.
4. Switch to **Refusal** to see the abstention mechanism.
5. Switch to **Degraded** to see the LLM failure fallback.
6. Use **Live form** to upload your own CSV (`data/samples/example_saas.csv` is a ready fixture).

---

## CSV Format

The ingestion engine accepts CSVs in two shapes:

**Wide format** (one column per period):
```
metric_id,2026-01,2026-02,2026-03,2026-04,2026-05,2026-06
monthly_recurring_revenue_growth,7.2,6.8,4.1,2.3,-1.2,-3.5
churn_rate,2.1,2.3,2.8,3.5,4.2,5.1
```

**Transposed format** (one row per period):
```
period,monthly_recurring_revenue_growth,churn_rate
2026-01,7.2,2.1
2026-02,6.8,2.3
...
```

The parser auto-detects the shape. Unrecognised column names are surfaced in the mapping confirmation step.
