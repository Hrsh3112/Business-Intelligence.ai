# System Architecture

## Design Philosophy

Three invariants govern every engineering decision:

1. **Deterministic quantitative core.** All anomaly detection, z-score calculations, percentile benchmarks, and severity scoring are mathematical and fully reproducible.
2. **Defensive orchestration.** Sub-engine failures (LLM timeouts, contract violations) degrade gracefully. The user always sees a result, never a raw traceback.
3. **Honest abstention.** When statistical support is insufficient the engine refuses to guess — returning diagnostic guidance instead of speculative analysis.

---

## Component Responsibilities

| Component | Directory | Owns |
|---|---|---|
| **C1** | `backend/core/ml_engine` | Synthetic baselines, noise sieve, severity scoring, refusal gate |
| **C2** | `backend/api/api` | Input parsing, schema validation, pipeline orchestration, API surface, frontend |
| **C3** | `backend/enrichment/c3_engine` | Anomaly clustering, prescriptions, case retrieval, LLM narrative |

---

## C1: Core Statistical Engine

**Entry point:** `ml_engine.analyze_company(CompanyInput) -> AnomalyReport`

**Processing stages:**

```
CompanyInput
    |
    +--> Refusal Gate: series length < 6 periods? -> RefusalDetail
    |
    +--> Synthetic Baseline Calibration
    |       Sector config (YAML) + revenue band -> per-metric mean/std
    |
    +--> Feature Extraction
    |       Weighted slope, curvature, acceleration, volatility
    |
    +--> Normalization
    |       Z-scores and percentiles against synthetic baseline
    |
    +--> 4-Layer Noise Sieve
    |       L1: |z| >= 1.5  (statistical magnitude)
    |       L2: >= 2 consecutive deviating periods (persistence)
    |       L3: correlated metric agreement (cross-metric)
    |       L4: seasonality / contextual adjustment
    |
    +--> Severity Scoring (0-100)
    |       Weighted: magnitude + slope + duration + correlation support
    |
    +--> Exclusive Classification
    |       INFO < 25 | WARNING < 50 | CRITICAL < 75 | SEVERE >= 75
    |
    +--> Deterministic NL Summary (template, no LLM)
    |
    `-> AnomalyReport (schema: anomaly_report_v1)
```

---

## C3: Enrichment Engine

**Entry point:** `c3_engine.enrich_report(AnomalyReport) -> EnrichedReport`

**Processing stages:**

```
AnomalyReport
    |
    +--> Gate 0: refusal pass-through (no further processing)
    |
    +--> Graph-Based Anomaly Clustering
    |       Connected components over Pearson correlation graph
    |
    +--> Deterministic Prescription Engine
    |       (sector, metric_id) -> rule table -> target delta
    |       No LLM. Every target is the sector synthetic baseline.
    |
    +--> Case-Based Retrieval
    |       Jaccard similarity: cluster context_tags vs case_studies.json
    |       Threshold: 0.30, top 2 matches per cluster
    |
    +--> LLM Narrative Synthesis (ONLY LLM CALL IN PIPELINE)
    |       Model: Gemini 2.0 Flash
    |       Output: structured JSON -> Narrative schema
    |       Fallback: degraded=True, narrative=None
    |
    `-> EnrichedReport (schema: enriched_report_v1)
```

---

## C2: Orchestration Pipeline

**File:** `backend/api/api/orchestration/pipeline.py`

```
run_pipeline(CompanyInput)
    |
    +--> Stage 1: C1 (in asyncio.to_thread, timeout=C1_TIMEOUT_S)
    |       Timeout / Exception -> status=failed, error=C1_TIMEOUT
    |
    +--> Refusal short-circuit
    |       If report.refusal is not None -> status=refused, skip C3
    |
    +--> Stage 2: C3 (in asyncio.to_thread, timeout=C3_TIMEOUT_S)
    |       Timeout  -> degraded=True, reason=c3_timeout
    |       Contract violation -> degraded=True, reason=c3_contract_violation
    |       Exception -> degraded=True, reason=c3_failed
    |
    `-> ApiResponse with Timings (c1_ms, c3_ms, total_ms)
```

**Status semantics:**

| Status | Meaning | result field |
|---|---|---|
| `complete` | Pipeline ran (includes degraded) | populated |
| `refused` | C1 declined — insufficient evidence | populated (bare wrap) |
| `failed` | C1 unavailable — nothing to show | None |

---

## Failure Paths

```
LLM timeout/failure
  -> C3 catches internally -> narrative=None, degraded=True
  -> Frontend: DegradedBanner shown, all statistical output still visible

C3 contract violation (schema drift)
  -> Orchestrator catches -> substitutes original AnomalyReport
  -> degraded=True displayed, no data loss

C1 timeout/failure
  -> Pipeline returns status=failed
  -> Frontend: error message (no results to show)

Input < 6 periods (any metric)
  -> C1 returns RefusalDetail -> status=refused
  -> Frontend: RefusalView (not an error, system working as designed)
```
