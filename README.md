# businessintelligence.ai

**KPI Intelligence-to-Action Engine** — a working prototype for the Accenture Innovation Challenge 2026, Problem Statement 3 (Round 2).

The system detects material KPI movements, reconciles data across heterogeneous sources, identifies and ranks explanatory drivers using deterministic and statistical methods, generates persona-specific narratives backed by traceable evidence, abstains when evidence is insufficient or contradictory, and recommends structured actions grounded in verifiable business logic — all within enforced latency and cost constraints.

---

## Core Design Principle

**The LLM is not the source of quantitative truth.**

Every number the user sees is computed before the LLM is invoked. Anomaly detection, z-score calculations, severity scoring, driver ranking, prescription targets, and confidence measures are all executed deterministically. The LLM has exactly one role in this pipeline: synthesising pre-computed, structured facts into readable prose. When it fails, the system degrades gracefully — every statistical output remains visible.

This distinction is explicitly documented, verifiable in the source, and enforced architecturally.

---

## Problem Statement Coverage

| PS Requirement | Implementation |
|---|---|
| 1. Detect and prioritise material KPI movements | 4-layer noise sieve + 0–100 severity scoring → INFO / WARNING / CRITICAL / SEVERE |
| 2. Reconcile data across heterogeneous sources | Mixed-granularity reconciliation (daily CRM downsampled to monthly ERP grain); source manifest with per-metric grain, freshness, and confidence |
| 3. Identify and rank explanatory drivers | Driver rank (primary driver vs. symptom), lead-lag heuristics, candidate explanations for low-confidence signals |
| 4. Generate persona-specific narratives | API-key-resolved persona (executive vs. analyst); structurally different LLM prompts; server-side field redaction |
| 5. Communicate uncertainty and abstain | Contradictory-evidence refusal; sparse-history refusal; degraded mode with visible banner; competing hypotheses when confidence < 0.5 |
| 6. Recommend structured actions | Full action schema: driver → controllable lever → action → expected impact → owner → confidence → monitoring plan |
| 7. Learn from feedback | Structured feedback log (verdict + correction type): first hop of a living knowledge base |
| 8. Security, cost, latency, scalability | API-key authentication, server-side persona entitlements, per-field response redaction, per-stage async timeouts, LLM cost estimation, token telemetry |

---

## Minimum Prototype Requirements Checklist

| Requirement | Status | Details |
|---|---|---|
| 3–5 connected KPIs across 2–3 sources with different grains | Implemented | Up to 7 KPIs (SaaS sector) or 7 KPIs (Retail); mixed CRM (daily) + ERP (monthly) granularity reconciliation |
| Lightweight KPI / semantic contract | Implemented | Machine-readable YAML per sector; `GET /metrics/{sector_id}` exposes definitions, calculation formulas, correlation matrix, drivers, role-based access restrictions, and lineage at runtime |
| At least 2 personas with different narratives or actions | Implemented | `executive` and `analyst` personas; different LLM prompt templates; analyst-only fields redacted for executive |
| One multi-factor KPI movement with known drivers | Implemented | Critical scenario: MRR collapse + churn surge + CAC inflation, correlated via Pearson graph and co-movement cluster |
| One low-confidence scenario — abstain or request clarification | Implemented | `noise_confidence < 0.5` triggers competing explanations; contradictory evidence triggers a full refusal with diagnostics |
| One sparse-history / newly launched KPI scenario | Implemented | Series with fewer than 6 periods triggers a structured `INSUFFICIENT_PERIODS` refusal |
| One role-based security / entitlement scenario | Implemented | `X-Api-Key` header resolves persona server-side; analyst-depth fields stripped from executive response |
| Evidence showing freshness, method, contribution, confidence, lineage | Implemented | Source manifest panel: grain, as-of period, interpolated points, confidence, source basis |
| Clear LLM vs. non-LLM breakdown | Implemented | Documented in `docs/llm-vs-deterministic.md` and verifiable via `grep -rn "genai" backend/core/` |
| Runtime telemetry: latency, model calls, token usage, cost | Implemented | `timings` (C1/C3/total ms), `cost` (model, tokens, estimated USD, basis) on every `ApiResponse` |

---

## System Architecture

The pipeline is divided into three independent components with strict schema contracts between them.

```
User (CSV upload or JSON POST)
         |
         v
C2: Ingestion & Orchestration
  Schema validation, column mapping, alias resolution
  Period normalisation, mixed-grain reconciliation
  Role-based persona resolution (X-Api-Key)
         | CompanyInput
         v
C1: Core Statistical Engine
  Synthetic baseline calibration  (sector YAML + revenue band)
  Feature extraction              (slope, curvature, acceleration, volatility)
  4-Layer Noise Sieve:
    L1  Statistical magnitude     |z| >= 1.5
    L2  Temporal persistence      >= 2 consecutive deviating periods
    L3  Cross-metric correlation  Pearson co-movement agreement
    L4  Contextual / seasonality  Business rules + domain config
  Driver ranking                  (primary driver vs. symptom, lead-lag)
  Severity scoring                0-100  ->  INFO / WARNING / CRITICAL / SEVERE
  Decision urgency                ESCALATING / STABLE_BAD / IMPROVING
  Refusal gate                    sparse history, contradictory evidence
  Template-based NL summary       (no LLM)
         | AnomalyReport
         v
C3: Enrichment Engine
  Graph-based anomaly clustering  (connected components over correlation graph)
  Deterministic prescription engine  (rule table -> target delta, owner, monitoring plan)
  Case-based retrieval            (Jaccard tag similarity, threshold 0.30)
  LLM narrative synthesis         (Gemini 2.0 Flash, structured JSON, exactly 1 call)
         | EnrichedReport
         v
C2: Response Assembly
  Source manifest generation      (lineage, grain, freshness)
  Persona-based field redaction   (server-side, recursive)
  Cost estimation                 (token count x model pricing)
  Telemetry aggregation           (C1 ms, C3 ms, total ms)
         |
         v
Next.js Executive UI
  Health score, anomaly cards, sparklines, severity bars,
  prescription cards, matched cases, executive narrative,
  source manifest panel, telemetry chip, feedback controls,
  degraded banner, refusal view
```

---

## LLM vs. Deterministic Breakdown

Every pipeline stage uses the method most appropriate for the task. The following table maps each stage to its technique and the rationale.

| Stage | Method | Technique | Why not LLM? |
|---|---|---|---|
| Input validation & schema | Deterministic | Pydantic v2, regex normalizers | Zero tolerance for schema violations |
| Refusal / abstention gate | Deterministic | Discrete boundary check (N < 6, contradictory signals) | Must be auditable and reproducible |
| Synthetic baseline generation | Statistical | Parameterized distribution sampling (normal / lognormal) | Reproducible sector benchmarks; no training data required |
| Feature extraction | Deterministic math | Weighted slope, curvature, acceleration, volatility | Closed-form; identical input produces identical output |
| Z-score normalisation | Statistics | Z-score, percentile rank against synthetic baseline | Standard parametric deviation measurement |
| L1 Statistical magnitude | Deterministic | Threshold: abs(z) >= 1.5 | Hard cutoff; no probabilistic wiggle room |
| L2 Temporal persistence | Deterministic | >= 2 consecutive deviating periods | Eliminates one-off data errors deterministically |
| L3 Cross-metric correlation | Statistics | Pearson correlation | Quantified directional relationship between business metrics |
| L4 Contextual filter | Business rules | Context tags + seasonality config | Domain knowledge encoded as rules, not approximated by a model |
| Driver ranking | Deterministic + graph | Cluster graph analysis, lead-lag heuristics, metric importance | Consistent, auditable ranking across runs |
| Decision urgency | Deterministic | Temporal slope + second-derivative acceleration | Crisp urgency signal grounded in measured trajectory |
| Severity scoring | Deterministic formula | Weighted linear combination (magnitude, slope, duration, correlation) | Consistent 0-100 score for cross-metric and cross-time comparison |
| NL summary (C1) | Template generation | String formatting | Reproducible, factually grounded text; LLM risks hallucination on numbers |
| Anomaly clustering | Graph algorithms | Connected components over Pearson correlation graph | Mathematically precise grouping |
| Prescription targets | Business rule table | (sector, metric) -> delta, owner, monitoring plan | Grounded in verified operational levers; guarantees realistic targets |
| Case retrieval | Information retrieval | Jaccard index over context tags | Fast, deterministic, fully auditable |
| Executive narrative | **LLM — Gemini 2.0 Flash** | Structured JSON output with schema enforcement | Optimal LLM task: synthesising pre-computed multidimensional data into clear prose |

**LLM usage is exactly one call per full analysis, or zero calls in degraded mode.**

To verify independently:

```bash
# C1 and C2: no LLM at all
grep -rn "genai" backend/core/ backend/orchestrator/   # returns nothing

# C3: exactly one module imports the LLM client
grep -rln "genai" backend/enrichment/ --include=*.py
#   backend/enrichment/c3_engine/narrative.py
#   backend/enrichment/test_c3.py
```

---

## Persona System and Role-Based Security

Persona is resolved server-side from an API key — the client cannot self-declare.

```
Request header:  X-Api-Key: exec-demo-key    ->  persona = executive
Request header:  X-Api-Key: analyst-demo-key ->  persona = analyst
```

**Narrative differentiation.** The LLM receives structurally different prompts per persona:

- `executive` — strategic language, concise (3–4 sentences), no statistical jargon, business-impact framing
- `analyst` — comprehensive depth (5–8 sentences), observed vs. expected values, co-movement patterns, causal mechanisms

**Field-level response redaction.** After the pipeline runs, C2 strips analyst-depth fields from the response for executive callers:

| Redacted for executive | Visible to analyst |
|---|---|
| `z_score` | `z_score` |
| `noise_confidence` | `noise_confidence` |
| `slope` | `slope` |
| `acceleration` | `acceleration` |
| `driver_rank` | `driver_rank` |

Redaction is applied recursively to the full enriched report before it leaves the API boundary.

---

## Abstention and Uncertainty Handling

The system communicates uncertainty explicitly rather than generating speculative output.

**Hard refusals** — the pipeline returns `status: refused` and does not invoke C3 or the LLM:

| Condition | Trigger |
|---|---|
| `INSUFFICIENT_PERIODS` | Any submitted metric has fewer than 6 time-series periods |
| `CONTRADICTORY_EVIDENCE` | Submitted signals violate established sector correlation properties |
| `LOW_DATA_CONFIDENCE` | All submitted metrics fall below the confidence threshold |
| `NO_METRICS_SUBMITTED` | Zero columns resolved to a recognised metric ID |

**Soft uncertainty** — the pipeline completes but flags competing hypotheses:

When a detected anomaly has `noise_confidence < 0.5`, the system generates `candidate_explanations` — a list of competing deterministic hypotheses. The LLM is explicitly instructed not to state a single definitive root cause for these metrics, instead presenting open hypotheses and noting that more data is required.

**Degraded mode** — full statistical output with LLM narrative suppressed:

When the LLM call fails, times out, or the API key is absent, the pipeline returns `status: complete` with `degraded: true`. All anomaly cards, severity scores, prescriptions, and matched cases remain visible. The UI displays a degraded banner. The system never returns a raw traceback.

---

## Action Recommendation Schema

Prescriptions follow the structure required by the problem statement:

```
driver -> controllable lever -> action -> expected impact -> owner -> confidence -> monitoring plan
```

Each `Adjustment` object in the API response carries:

| Field | Description |
|---|---|
| `target_metric_id` | The KPI being addressed |
| `action` | `INCREASE` or `DECREASE` |
| `current_value` | Observed value from submitted data |
| `target_value` | Deterministic target derived from sector synthetic baseline |
| `delta` | Computed gap |
| `priority` | `HIGH` / `MEDIUM` / `LOW` |
| `rationale` | Grounded in sector benchmarks |
| `controllable_lever` | The specific operational lever (e.g., "Sales pipeline velocity & marketing spend allocation") |
| `expected_impact` | Stated business outcome (e.g., "Accelerates new customer acquisition") |
| `owner` | Named role responsible (e.g., "VP of Sales / Chief Revenue Officer") |
| `action_confidence` | `HIGH` / `MEDIUM` / `LOW` |
| `monitoring_plan` | Concrete cadence and metric to watch |

Every prescription target is the sector's synthetic baseline value — not a generated estimate. Owner and monitoring plan are drawn from a verified domain rule table, not inferred by the LLM.

---

## KPI Semantic Contract

The contract is machine-readable (YAML, served at runtime via `GET /metrics/{sector_id}`) and human-readable. It governs metric definitions, accepted aliases, valid ranges, optimization direction, and baseline weights used in health score computation.

**Supported sectors:**

| Sector | KPIs |
|---|---|
| `TECH_SAAS` | MRR Growth Rate, Monthly Churn Rate, Customer Acquisition Cost, Customer Lifetime Value, Net Revenue Retention, Monthly Burn Rate, Gross Margin |
| `RETAIL` | Gross Margin, Inventory Turnover, Average Order Value, Revenue per Sq Ft, Same Store Sales Growth, Sell-Through Rate, Product Return Rate |

**Severity classification:**

| Band | Score Range | Operational Meaning |
|---|---|---|
| INFO | 0.0 - 24.9 | Logged for trend tracking; no immediate action required |
| WARNING | 25.0 - 49.9 | Weekly review; monitor trajectory |
| CRITICAL | 50.0 - 74.9 | Cross-functional review; operational adjustments required |
| SEVERE | 75.0 - 100.0 | Executive escalation; immediate intervention |

**Revenue band calibration:** Synthetic baselines are parameterised per `(sector_id, revenue_band)` combination across five bands (< $1M, $1M–$10M, $10M–$50M, $50M–$100M, > $100M). Health score weights scale dynamically by the company's revenue cohort.

---

## Feedback and Learning

The system captures structured analyst feedback per report, per narrative, and per individual anomaly via `POST /feedback`.

Each feedback record includes:

| Field | Description |
|---|---|
| `job_id` | Links back to the specific analysis run |
| `target` | `report`, `narrative`, or `anomaly` |
| `verdict` | `useful` or `not_useful` |
| `correction` | `was_noise`, `severity_understated`, `severity_overstated`, `wrong_root_cause` |
| `comment` | Free text, capped at 2,000 characters |

Feedback is stored as append-only structured JSONL. The correction field is an enumerated type rather than free text, making the log machine-aggregatable and suitable for driving threshold calibration or case-base updates as the next step. This is the first hop of a living knowledge base; any claim beyond structured capture is noted in the source as out of scope for this prototype.

---

## Runtime Telemetry

Every `ApiResponse` includes a `timings` block and a `cost` block:

```json
{
  "timings": {
    "c1_ms": 42,
    "c3_ms": 1380,
    "total_ms": 1423
  },
  "cost": {
    "llm_model": "gemini-2.0-flash",
    "tokens_used": 2847,
    "estimated_usd": 0.000427,
    "basis": "input+output token count x model list price"
  }
}
```

- `c1_ms` — time spent in the statistical engine (deterministic path)
- `c3_ms` — time spent in the enrichment engine including the LLM call
- `total_ms` — wall-clock time from request receipt to response dispatch
- `estimated_usd` is `null` when the LLM did not run or the model is unpriced; it is never reported as zero to mask an unknown

---

## Demo Scenarios

The web application ships with four pre-generated scenario fixtures demonstrating the full range of pipeline states. The Scenario Switcher (visible when `NEXT_PUBLIC_SHOW_SCENARIO_SWITCHER=true`) lets evaluators cycle through all pipeline states without a specific CSV upload.

| Scenario | What it demonstrates |
|---|---|
| **Critical (SEVERE)** | Multi-factor correlated movement: MRR collapse + churn surge + CAC inflation. Driver ranking, co-movement cluster, case retrieval, persona-tailored executive narrative. |
| **Healthy** | All metrics within synthetic baseline bounds. Positive highlights, no prescriptions triggered, health score in the green band. |
| **Refusal** | Sparse history scenario: fewer than 6 periods triggers a structured `INSUFFICIENT_PERIODS` refusal with diagnostic remediation steps. No LLM call; no cost. |
| **Degraded** | Simulated LLM failure: full statistical output remains visible, degraded banner displayed, `degraded: true` in the API response. |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Statistical engine (C1) | Python 3.11, NumPy, SciPy, NetworkX, PyYAML |
| Enrichment engine (C3) | Python 3.11, Google Generative AI SDK (Gemini 2.0 Flash) |
| API & orchestration (C2) | FastAPI, Pydantic v2, asyncio |
| Frontend | Next.js 15, React 19, TypeScript |
| Configuration | YAML sector configs, environment variables |
| Testing | pytest (340 tests, 0 failures) |

---

## Project Structure

```
.
+-- backend/
|   +-- core/ml_engine/          # C1: statistical engine, noise sieve, severity, refusal gate
|   |   +-- anomaly/             # Detector, noise filter, scorer, classifier, refusal, summary
|   |   +-- features/            # Feature extraction, z-score normalisation
|   |   +-- synthetic/           # Baseline calibration (sector YAML + revenue band)
|   |   +-- models/              # Input and output schemas
|   |   `-- config/sectors/      # tech_saas.yaml, retail.yaml (metric params + weights)
|   |
|   +-- enrichment/c3_engine/    # C3: clustering, prescriptions, case retrieval, LLM narrative
|   |   +-- clustering.py        # Graph-based anomaly clustering
|   |   +-- prescriptions.py     # Rule table -> full action schema
|   |   +-- case_matcher.py      # Jaccard similarity retrieval
|   |   +-- narrative.py         # Single LLM call, persona-differentiated prompt
|   |   `-- schemas.py           # EnrichedReport, Prescription, Adjustment, Narrative
|   |
|   `-- orchestrator/api/        # C2: FastAPI app, parsing, pipeline, routes, models
|       +-- routes/              # /analyze, /analyze/upload, /feedback, /metrics, /health
|       +-- parsing/             # CSV ingestion, column mapping, lineage, gap-filling
|       +-- orchestration/       # Pipeline runner, C1/C3 adapters, degradation wrappers
|       +-- models/              # Shared schemas, internal models, response filter
|       `-- config/              # Auth, pricing, sector loader, settings
|
+-- web/src/
|   +-- app/                     # Next.js App Router pages and layout
|   +-- components/              # AnomalyCard, PrescriptionCard, Narrative, SourceManifestPanel,
|   |                            # PersonaSwitcher, FeedbackControl, TelemetryChip, RefusalView,
|   |                            # DegradedBanner, MethodPanel, SeverityConfidenceBar, Sparkline
|   +-- lib/                     # API client, scenario fixtures, utilities
|   `-- types/                   # TypeScript interfaces for all API response shapes
|
+-- data/samples/                # Sample CSV files for testing and demo
+-- data/crm_fixture.json        # Daily CRM sample fixture for multi-source ingestion testing
+-- docs/                        # Architecture, KPI contract, LLM vs. deterministic, quickstart
+-- scripts/                     # dump_scenario_responses.py (generates fixture JSON)
+-- .env.example                 # Environment configuration template
+-- start.ps1                    # One-command startup (Windows / PowerShell)
`-- start.sh                     # One-command startup (Linux / macOS)
```

---

## Quick Start

### Prerequisites

- Python >= 3.11
- Node.js >= 18
- A Gemini API key (optional — the system runs in deterministic-only mode without one)

### 1. Configure environment

```bash
cp .env.example .env
# Add GEMINI_API_KEY for live narrative synthesis
# Set EXEC_API_KEY and ANALYST_API_KEY for persona-resolved access
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

- Backend API: `http://localhost:8000` — Swagger UI at `/docs`
- Web Application: `http://localhost:3000`

### 4. Run tests

```bash
pytest backend/
# 340 passed
```

---

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Component responsibilities, pipeline stages, failure paths |
| [KPI Semantic Contract](docs/kpi-semantic-contract.md) | Metric definitions, baselines, severity thresholds, lineage |
| [LLM vs. Deterministic](docs/llm-vs-deterministic.md) | Per-stage method breakdown with rationale |
| [Quickstart](docs/quickstart.md) | Step-by-step local setup and deployment guide |
