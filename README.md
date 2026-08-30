# businessintelligence.ai

**KPI Intelligence-to-Action Engine** — a working prototype for the Accenture Innovation Challenge 2026.

The system detects material KPI movements, reconciles data across heterogeneous sources, identifies and ranks explanatory drivers using statistical and machine-learning methods, generates persona-specific narratives backed by traceable evidence, abstains when evidence is insufficient or contradictory, and recommends structured actions grounded in verifiable business logic — all within enforced latency and cost constraints.

---

## Core Design Principle

**The LLM is not the source of quantitative truth.**

Every number the user sees is computed before the LLM is ever invoked. Anomaly detection, z-score calculations, time-series forecasting, multivariate outlier detection, causal driver ranking, severity scoring, prescription targets, and confidence measures are all executed deterministically or via named, auditable ML models. The LLM has exactly one role in this pipeline: synthesising pre-computed, structured facts into readable prose. When it fails, the system degrades gracefully — every statistical and ML output remains visible.

This distinction is explicitly documented, verifiable in the source, and enforced architecturally.

---

## Problem Statement Coverage

| Requirement | Implementation |
|---|---|
| 1. Detect and prioritise material KPI movements | 5-layer noise sieve (4 statistical/rule layers + Isolation Forest multivariate layer) + 0–100 severity scoring → INFO / WARNING / CRITICAL / SEVERE |
| 2. Reconcile data across heterogeneous sources | Mixed-granularity reconciliation (daily CRM downsampled to monthly ERP grain); source manifest with per-metric grain, freshness, and confidence |
| 3. Identify and rank explanatory drivers | Granger causality for temporal driver direction (≥10 periods); cluster magnitude heuristic fallback; lead-lag analysis; candidate explanations for low-confidence signals |
| 4. Generate persona-specific narratives | API-key-resolved persona (executive vs. analyst); structurally different LLM prompts; server-side field redaction |
| 5. Communicate uncertainty and abstain | Contradictory-evidence refusal; sparse-history refusal; degraded mode with visible banner; competing hypotheses when confidence < 0.5 |
| 6. Recommend structured actions | Full action schema: driver → controllable lever → action → expected impact → owner → confidence → monitoring plan |
| 7. Learn from feedback | Beta-Binomial Bayesian recalibration: analyst feedback actively adjusts anomaly detection thresholds per (sector, metric) pair |
| 8. Security, cost, latency, scalability | API-key authentication, server-side persona entitlements, per-field response redaction, per-stage async timeouts, LLM cost estimation, token telemetry |

---

## Machine Learning System

The detection engine combines four complementary methods — two time-series models, one unsupervised ML model, and one causal inference test — layered on top of a deterministic rule pipeline.

### Holt-Winters ETS — Personalised Baseline Forecasting

**What it does:** Fits a Holt-Winters Exponential Smoothing (ETS) model on the *user's own historical data* and uses the one-step-ahead forecast as the expected value for anomaly detection. The baseline becomes personalised to the company's own trajectory rather than relying solely on sector-wide averages.

**Why it matters:** The LLM is explicitly *not* doing any forecasting — a named, auditable time-series model is. This is the strongest possible evidence for the LLM / non-LLM separation the problem statement requires.

| Detail | Value |
|---|---|
| Model | Holt-Winters ETS (additive trend, damped) |
| Library | `statsmodels.tsa.holtwinters.ExponentialSmoothing` |
| Activation | When ≥ 6 periods of history are submitted |
| Fallback | Sector-parametric synthetic baseline for < 6 periods |
| Transparency | `baseline_source` field on every anomaly card: `ets_personalised` or `sector_parametric` |

### Isolation Forest — Multivariate Anomaly Detection

**What it does:** A dedicated detection layer runs `sklearn.ensemble.IsolationForest` on the full cross-metric value matrix. It flags periods where the *combination* of metric values is anomalous, even if no single metric crosses the univariate z-score threshold — catching the "multiple interacting drivers each moving slightly" pattern the problem statement explicitly highlights.

| Detail | Value |
|---|---|
| Model | Isolation Forest (unsupervised) |
| Library | `sklearn.ensemble.IsolationForest` |
| Activation | When ≥ 2 metrics and ≥ 8 periods are available |
| Seed | `random_state=42` for full reproducibility |
| Output | Anomalies tagged `multivariate_pattern` in context tags |

### Granger Causality — Driver Directionality

**What it does:** Within each correlated anomaly cluster, Granger causality tests determine the *direction* of influence between metrics. The metric whose lagged values best predict others is promoted as the structural driver. Prior implementations used correlation magnitude alone — symmetric and unable to determine which metric leads.

**Honest labelling:** Granger tests temporal precedence, not structural causation. The system labels this "Granger lead-lag test" and does not overclaim causal status.

| Detail | Value |
|---|---|
| Test | Granger causality (F-test, SSR) |
| Library | `statsmodels.tsa.stattools.grangercausalitytests` |
| Activation | When ≥ 10 periods available; heuristic fallback otherwise |
| Parameters | `max_lag=2`, `p < 0.05` |
| Transparency | `granger_tested: true/false` visible per anomaly |

### Beta-Binomial Bayesian Recalibration — Learning from Feedback

**What it does:** Closes the feedback loop. Analyst ratings ("useful" / "not useful") from the feedback panel are consumed by a Beta-Binomial conjugate update that adjusts the anomaly detection z-score threshold per `(sector, metric)` pair. Thresholds are cached and applied on every subsequent analysis run — the system measurably changes its behaviour based on human feedback.

| Detail | Value |
|---|---|
| Method | Beta-Binomial Bayesian update |
| Prior | Beta(1, 1) — uniform, no bias |
| Cold-start guard | Requires ≥ 5 feedback points before any adjustment |
| Cap | Threshold never exceeds `base + 0.8` (prevents over-sensitivity) |
| Cache | 60-second TTL per `(sector, feedback_log_path)` |

### Method Transparency Panel

Every analysis response includes a live **"How we did this"** panel in the UI. It lists every pipeline stage, its method type (ML / Statistical / Deterministic / LLM), and the specific technique — including the real model name and token count for the LLM call. The LLM row dynamically reads from the API response, showing "not called" on refusal or degraded runs rather than making a static false claim.

---

## System Architecture

The pipeline is divided into three logical stages with strict schema contracts between them.

```
User (CSV upload or JSON POST)
         |
         v
Ingestion & Orchestration Layer
  Schema validation, column mapping, alias resolution
  Period normalisation, mixed-grain reconciliation
  Role-based persona resolution (X-Api-Key)
         | CompanyInput
         v
Statistical & ML Detection Engine
  Synthetic baseline calibration  (sector YAML + revenue band)
  ETS personalised baseline       (Holt-Winters, >= 6 periods)
  Feature extraction              (slope, curvature, acceleration, volatility)
  5-Layer Noise Sieve:
    L1   Statistical magnitude     |z| >= threshold (Bayesian-recalibrated per metric)
    L1b  Multivariate detection    Isolation Forest (>= 2 metrics, >= 8 periods)
    L2   Temporal persistence      >= 2 consecutive deviating periods
    L3   Cross-metric correlation  Pearson co-movement agreement
    L4   Contextual / seasonality  Business rules + domain config
  Driver ranking                  Granger causality (>= 10 periods) or magnitude heuristic
  Severity scoring                0-100  ->  INFO / WARNING / CRITICAL / SEVERE
  Decision urgency                ESCALATING / STABLE_BAD / IMPROVING
  Refusal gate                    sparse history, contradictory evidence
  Template-based NL summary       (no LLM)
         | AnomalyReport
         v
Enrichment & Narrative Engine
  Graph-based anomaly clustering  (connected components over correlation graph)
  Deterministic prescription engine  (rule table -> target delta, owner, monitoring plan)
  Case-based retrieval            (Jaccard tag similarity, threshold 0.30)
  LLM narrative synthesis         (Gemini 2.0 Flash, structured JSON, exactly 1 call)
         | EnrichedReport
         v
Response Assembly Layer
  Source manifest generation      (lineage, grain, freshness)
  Persona-based field redaction   (server-side, recursive)
  Cost estimation                 (token count x model pricing)
  Telemetry aggregation           (detection ms, enrichment ms, total ms)
         |
         v
Next.js Executive UI
  Health score, anomaly cards, sparklines, severity bars,
  prescription cards, matched cases, executive narrative,
  source manifest panel, telemetry chip, feedback controls,
  method panel, degraded banner, refusal view
```

---

## LLM vs. Non-LLM Breakdown

Every pipeline stage uses the method most appropriate for the task. The following table maps each stage to its technique and rationale.

| Stage | Method | Technique | Why not LLM? |
|---|---|---|---|
| Input validation & schema | Deterministic | Pydantic v2, regex normalizers | Zero tolerance for schema violations |
| Refusal / abstention gate | Deterministic | Discrete boundary check (N < 6, contradictory signals) | Must be auditable and reproducible |
| Synthetic baseline generation | Statistical | Parameterized distribution sampling (normal / lognormal) | Reproducible sector benchmarks; no training data required |
| ETS personalised baseline | **ML — Time Series** | Holt-Winters ETS (statsmodels, additive trend, damped) | Named forecasting model; not a generated estimate |
| Feature extraction | Deterministic math | Weighted slope, curvature, acceleration, volatility | Closed-form; identical input → identical output |
| Z-score normalisation | Statistics | Z-score, percentile rank against synthetic baseline | Standard parametric deviation measurement |
| L1 Statistical magnitude | Deterministic | Bayesian-recalibrated threshold abs(z) >= threshold | Hard cutoff; per-metric threshold adjusted from feedback |
| L1b Multivariate detection | **ML — Unsupervised** | Isolation Forest (sklearn, contamination=0.1) | Catches combination anomalies invisible to univariate tests |
| L2 Temporal persistence | Deterministic | >= 2 consecutive deviating periods | Eliminates one-off data errors deterministically |
| L3 Cross-metric correlation | Statistics | Pearson correlation | Quantified directional relationship between business metrics |
| L4 Contextual filter | Business rules | Context tags + seasonality config | Domain knowledge encoded as rules, not approximated by a model |
| Driver ranking | **ML — Causal Inference** | Granger causality (statsmodels, max_lag=2, p<0.05) | Tests temporal precedence; upgrades symmetric correlation to directed graph |
| Decision urgency | Deterministic | Temporal slope + second-derivative acceleration | Crisp urgency signal grounded in measured trajectory |
| Severity scoring | Deterministic formula | Weighted linear combination (magnitude, slope, duration, correlation) | Consistent 0-100 score for cross-metric comparison |
| NL summary | Template generation | String formatting | Reproducible, factually grounded text; LLM risks hallucination on numbers |
| Anomaly clustering | Graph algorithms | Connected components over Pearson correlation graph | Mathematically precise grouping |
| Prescription targets | Business rule table | (sector, metric) → delta, owner, monitoring plan | Grounded in verified operational levers; guarantees realistic targets |
| Case retrieval | Information retrieval | Jaccard index over context tags | Fast, deterministic, fully auditable |
| Threshold recalibration | **ML — Bayesian** | Beta-Binomial conjugate update on analyst feedback | Named statistical learning algorithm; closes the feedback loop |
| Executive narrative | **LLM — Gemini 2.0 Flash** | Structured JSON output with schema enforcement | Optimal LLM task: synthesising pre-computed multidimensional data into clear prose |

**LLM usage is exactly one call per full analysis, or zero calls in degraded mode.**

To verify independently:

```bash
# Detection and orchestration layers: no LLM at all
grep -rn "genai" backend/core/ backend/orchestrator/   # returns nothing

# Enrichment layer: exactly one module imports the LLM client
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

**Field-level response redaction.** After the pipeline runs, the response assembly layer strips analyst-depth fields from the response for executive callers:

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

**Hard refusals** — the pipeline returns `status: refused` and does not invoke the LLM:

| Condition | Trigger |
|---|---|
| `INSUFFICIENT_PERIODS` | Any submitted metric has fewer than 6 time-series periods |
| `CONTRADICTORY_EVIDENCE` | Submitted signals violate established sector correlation properties |
| `LOW_DATA_CONFIDENCE` | All submitted metrics fall below the confidence threshold |
| `NO_METRICS_SUBMITTED` | Zero columns resolved to a recognised metric ID |

**Soft uncertainty** — the pipeline completes but flags competing hypotheses:

When a detected anomaly has `noise_confidence < 0.5`, the system generates `candidate_explanations` — a list of competing deterministic hypotheses. The LLM is explicitly instructed not to state a single definitive root cause for these metrics, instead presenting open hypotheses and noting that more data is required.

**Degraded mode** — full statistical and ML output with LLM narrative suppressed:

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
| INFO | 0.0 – 24.9 | Logged for trend tracking; no immediate action required |
| WARNING | 25.0 – 49.9 | Weekly review; monitor trajectory |
| CRITICAL | 50.0 – 74.9 | Cross-functional review; operational adjustments required |
| SEVERE | 75.0 – 100.0 | Executive escalation; immediate intervention |

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

Feedback is stored as append-only structured JSONL and immediately consumed by the Beta-Binomial recalibrator on the next analysis run. The correction field is an enumerated type rather than free text, making the log machine-aggregatable. This closes the complete feedback loop: human signal → Bayesian update → measurably adjusted system behaviour.

---

## Runtime Telemetry

Every `ApiResponse` includes a `timings` block and a `cost` block:

```json
{
  "timings": {
    "detection_ms": 42,
    "enrichment_ms": 1380,
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

- `detection_ms` — time spent in the statistical and ML detection engine (deterministic path)
- `enrichment_ms` — time spent in the enrichment engine including the LLM call
- `total_ms` — wall-clock time from request receipt to response dispatch
- `estimated_usd` is `null` when the LLM did not run or the model is unpriced; it is never reported as zero to mask an unknown

---

## Demo Scenarios

The web application ships with four pre-generated scenario fixtures demonstrating the full range of pipeline states. The Scenario Switcher (visible when `NEXT_PUBLIC_SHOW_SCENARIO_SWITCHER=true`) lets evaluators cycle through all pipeline states without a CSV upload.

| Scenario | What it demonstrates |
|---|---|
| **Critical (SEVERE)** | Multi-factor correlated movement: MRR collapse + churn surge + CAC inflation. Granger-ranked driver, co-movement cluster, Isolation Forest multivariate tag, case retrieval, persona-tailored executive narrative. |
| **Healthy** | All metrics within ETS/synthetic baseline bounds. Positive highlights, no prescriptions triggered, health score in the green band. |
| **Refusal** | Sparse history scenario: fewer than 6 periods triggers a structured `INSUFFICIENT_PERIODS` refusal with diagnostic remediation steps. No LLM call; no cost. |
| **Degraded** | Simulated LLM failure: full statistical and ML output remains visible, degraded banner displayed, `degraded: true` in the API response. |

---

## Minimum Prototype Requirements Checklist

| Requirement | Status | Details |
|---|---|---|
| 3–5 connected KPIs across 2–3 sources with different grains | ✅ Implemented | Up to 7 KPIs (SaaS) or 7 KPIs (Retail); mixed CRM (daily) + ERP (monthly) granularity reconciliation |
| Lightweight KPI / semantic contract | ✅ Implemented | Machine-readable YAML per sector; `GET /metrics/{sector_id}` exposes definitions, formulas, correlation matrix, drivers, role-based access, and lineage at runtime |
| At least 2 personas with different narratives or actions | ✅ Implemented | `executive` and `analyst` personas; different LLM prompt templates; analyst-only fields redacted for executive |
| One multi-factor KPI movement with known drivers | ✅ Implemented | Critical scenario: MRR collapse + churn surge + CAC inflation, correlated via Pearson graph and co-movement cluster, driver ranked by Granger causality |
| One low-confidence scenario — abstain or request clarification | ✅ Implemented | `noise_confidence < 0.5` triggers competing explanations; contradictory evidence triggers full refusal with diagnostics |
| One sparse-history / newly launched KPI scenario | ✅ Implemented | Series with fewer than 6 periods triggers a structured `INSUFFICIENT_PERIODS` refusal; ETS falls back to sector baseline |
| One role-based security / entitlement scenario | ✅ Implemented | `X-Api-Key` header resolves persona server-side; analyst-depth fields stripped from executive response |
| Evidence showing freshness, method, contribution, confidence, lineage | ✅ Implemented | Source manifest panel: grain, as-of period, interpolated points, confidence, source basis; `baseline_source` per anomaly |
| Clear LLM vs. non-LLM breakdown | ✅ Implemented | Documented in `docs/llm-vs-deterministic.md`, verifiable via `grep -rn "genai" backend/core/`, and surfaced live in the Method Panel UI |
| Runtime telemetry: latency, model calls, token usage, cost | ✅ Implemented | `timings` (detection/enrichment/total ms), `cost` (model, tokens, estimated USD, basis) on every `ApiResponse` |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Statistical & ML detection engine | Python 3.11, NumPy, SciPy, statsmodels ≥ 0.14 (ETS, Granger), scikit-learn ≥ 1.4 (Isolation Forest), NetworkX, PyYAML |
| Enrichment & narrative engine | Python 3.11, Google Generative AI SDK (Gemini 2.0 Flash) |
| API & orchestration | FastAPI, Pydantic v2, asyncio |
| Frontend | Next.js 15, React 19, TypeScript |
| Configuration | YAML sector configs, environment variables |
| Testing | pytest (340 tests, 0 failures) — 13 test modules covering all ML models and pipeline stages |

---

## Project Structure

```
.
+-- backend/
|   +-- core/ml_engine/          # Statistical & ML detection engine
|   |   +-- anomaly/             # Detector, noise filter (L1–L4 + Isolation Forest L1b),
|   |   |                        # causal engine (Granger), scorer, classifier, refusal, summary
|   |   +-- features/            # Feature extraction, z-score normalisation
|   |   +-- synthetic/           # Baseline calibration (sector YAML + ETS personalised baseline)
|   |   +-- config/              # Thresholds, sector loader, Bayesian feedback recalibrator
|   |   +-- models/              # Input and output schemas
|   |   `-- tests/               # 13 test modules: anomaly, ML models, pipeline E2E, refusal
|   |
|   +-- enrichment/c3_engine/    # Enrichment & narrative engine
|   |   +-- clustering.py        # Graph-based anomaly clustering
|   |   +-- prescriptions.py     # Rule table -> full action schema
|   |   +-- case_matcher.py      # Jaccard similarity retrieval
|   |   +-- narrative.py         # Single LLM call, persona-differentiated prompt
|   |   `-- schemas.py           # EnrichedReport, Prescription, Adjustment, Narrative
|   |
|   `-- orchestrator/api/        # FastAPI app, parsing, pipeline, routes, models
|       +-- routes/              # /analyze, /analyze/upload, /feedback, /metrics, /health
|       +-- parsing/             # CSV ingestion, column mapping, lineage, gap-filling
|       +-- orchestration/       # Pipeline runner, adapters, degradation wrappers
|       +-- models/              # Shared schemas, internal models, response filter
|       `-- config/              # Auth, pricing, sector loader, settings
|
+-- web/src/
|   +-- app/                     # Next.js App Router pages and layout
|   +-- components/              # AnomalyCard, PrescriptionCard, Narrative, SourceManifestPanel,
|   |                            # PersonaSwitcher, FeedbackControl, TelemetryChip, RefusalView,
|   |                            # DegradedBanner, MethodPanel, SeverityConfidenceBar, Sparkline
|   +-- lib/                     # API client, scenario fixtures, method definitions, utilities
|   `-- types/                   # TypeScript interfaces for all API response shapes
|
+-- data/samples/                # Sample CSV files for testing and demo
+-- data/crm_fixture.json        # Daily CRM sample fixture for multi-source ingestion testing
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
