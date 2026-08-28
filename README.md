# businessintelligence.ai

> **KPI Intelligence-to-Action Engine** — an autonomous, multi-layered decision intelligence system that detects material KPI anomalies, isolates structural deviations from statistical noise, retrieves proven operational playbooks, and generates persona-grounded executive narratives and corrective prescriptions.

Built for the **Accenture Innovation Challenge 2026 — Problem Statement 3 (Round 2)**.

---

## Core Principle

**The LLM is not the source of quantitative truth.**

All calculations, anomaly detection, severity grading, and corrective targets are executed deterministically before the LLM synthesises any narrative. Every number the user sees is computed — not generated.

---

## Architecture

```
[User / CSV Upload]
        |
        v
[C2: Parsing & Ingestion]
  Schema validation, metric mapping, period normalisation
        |  CompanyInput
        v
[C1: Core Statistical Engine]
  Synthetic baseline calibration (sector + revenue band)
  4-Layer Noise Filter Sieve:
    L1 — Statistical magnitude  (|z| >= 1.5)
    L2 — Temporal persistence   (>= 2 consecutive periods)
    L3 — Cross-metric correlation
    L4 — Contextual / seasonality filter
  Severity scoring 0-100 -> INFO / WARNING / CRITICAL / SEVERE
        |  AnomalyReport
        v
[C3: Enrichment & Narrative Engine]
  Graph-based anomaly clustering
  Deterministic prescriptions  (rule table -> target deltas)
  Case-based retrieval         (Jaccard tag similarity)
  LLM narrative synthesis      (Gemini 2.0 Flash, structured JSON)
        |  EnrichedReport
        v
[C2: FastAPI Orchestrator]
  Async timeout enforcement, degraded-mode cascade
  Telemetry aggregation (latency, token usage)
        |  ApiResponse
        v
[Next.js Executive UI]
  Health score, correlated anomaly cards, sparklines,
  prescriptions, matched cases, executive narrative
```

---

## Project Structure

```
.
|-- backend/                    # All Python services (one install)
|   |-- core/
|   |   `-- ml_engine/          # C1: anomaly detection & statistical engine
|   |-- enrichment/
|   |   `-- c3_engine/          # C3: clustering, prescriptions, case CBR, LLM
|   |-- api/
|   |   `-- api/                # C2: FastAPI orchestration, parsing, routes
|   |-- requirements.txt        # Unified Python dependencies
|   `-- pyproject.toml          # Unified package configuration
|
|-- web/                        # Next.js 15 / React 19 frontend
|   `-- src/
|       |-- app/                # App Router pages & layout
|       |-- components/         # Anomaly cards, sparklines, narrative, refusal
|       |-- lib/                # API client, scenario fixtures, utilities
|       `-- types/              # TypeScript OpenAPI interfaces
|
|-- data/
|   `-- samples/                # Sample CSV files for testing & demo
|       `-- example_saas.csv
|
|-- docs/                       # Technical documentation
|   |-- architecture.md         # Pipeline deep-dive & component breakdown
|   |-- kpi-semantic-contract.md# KPI definitions, baselines & thresholds
|   |-- llm-vs-deterministic.md # When & why each method is used
|   `-- quickstart.md           # Local setup & deployment guide
|
|-- scripts/
|   `-- dump_scenario_responses.py  # Generates canned demo scenario JSON
|
|-- .env.example                # Environment configuration template
|-- start.ps1                   # One-command startup (Windows)
|-- start.sh                    # One-command startup (Linux/macOS)
`-- README.md
```

---

## Quick Start

### Prerequisites
- Python >= 3.11
- Node.js >= 18
- A Gemini API key (optional for mock mode)

### 1. Configure environment
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY for live narrative synthesis
```

### 2. Install backend
```bash
pip install -e backend/
```

### 3. Launch the stack

**Windows (PowerShell):**
```powershell
.\start.ps1
```

**Linux / macOS:**
```bash
chmod +x start.sh && ./start.sh
```

- Backend API: **http://localhost:8000** (Swagger: http://localhost:8000/docs)
- Web App: **http://localhost:3000**

---

## Demo Scenarios

The web app includes a **Scenario Switcher** (bottom-right, visible when `NEXT_PUBLIC_SHOW_SCENARIO_SWITCHER=true`) to demonstrate all pipeline states without needing a specific CSV:

| Scenario | What it demonstrates |
|---|---|
| **Critical (SEVERE)** | Multi-factor detection: MRR collapse + churn surge + CAC inflation, correlated anomaly graph, case retrieval, executive narrative |
| **Healthy** | All metrics within synthetic baseline bounds, positive highlights |
| **Refusal** | Sparse history triggering transparent abstention with remediation steps |
| **Degraded** | LLM failure simulation; full deterministic fallback with zero UI crash |

---

## Running Tests

```bash
pytest backend/
```

---

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Pipeline deep-dive, component responsibilities, failure paths |
| [KPI Semantic Contract](docs/kpi-semantic-contract.md) | Metric definitions, baselines, severity thresholds |
| [LLM vs Deterministic](docs/llm-vs-deterministic.md) | Explicit method breakdown per pipeline stage |
| [Quickstart](docs/quickstart.md) | Step-by-step local setup |
