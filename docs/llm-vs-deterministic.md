# Methodology Breakdown: LLM vs. Deterministic

> The LLM is not the source of quantitative truth. This document records exactly when and why each method is used — as required by the problem statement.

---

## Pipeline Method Matrix

| Stage | File | Method | Technique | Why not LLM? |
|---|---|---|---|---|
| Input validation & schema | `api/parsing/` | **Deterministic** | Pydantic v2, regex normalizers | Zero tolerance for schema violations. LLMs are non-deterministic parsers. |
| Refusal / abstention gate | `ml_engine/anomaly/refusal.py` | **Deterministic** | Discrete boundary check (N < 6) | The decision to refuse must be auditable and reproducible. |
| Synthetic baseline generation | `ml_engine/synthetic/generator.py` | **Statistical** | Parameterized distribution sampling (normal/lognormal) | Generates reproducible sector benchmarks; no training data required. |
| Feature extraction | `ml_engine/features/extractor.py` | **Deterministic math** | Weighted slope, curvature, acceleration, volatility | Closed-form calculations. Identical input must produce identical output. |
| Z-score normalisation | `ml_engine/features/normalizer.py` | **Statistics** | Z-score, percentile rank | Standard parametric deviation measurement. |
| L1 — Statistical magnitude filter | `ml_engine/anomaly/noise_filter.py` | **Deterministic** | Threshold: |z| >= 1.5 | Hard cutoff; no probabilistic wiggle room. |
| L2 — Persistence filter | `ml_engine/anomaly/noise_filter.py` | **Deterministic** | >= 2 consecutive deviating periods | Temporal rule; eliminates one-off data errors deterministically. |
| L3 — Cross-metric correlation | `ml_engine/anomaly/noise_filter.py` | **Statistics** | Pearson correlation | Quantified directional relationship between business metrics. |
| L4 — Contextual/seasonality filter | `ml_engine/anomaly/noise_filter.py` | **Business rules** | Context tags + seasonality config | Domain knowledge encoded as rules, not approximated by a model. |
| Severity scoring | `ml_engine/anomaly/scorer.py` | **Deterministic formula** | Weighted linear combination | Consistent 0-100 score for comparison across metrics and time. |
| Severity classification | `ml_engine/anomaly/classifier.py` | **Deterministic** | Exclusive band thresholds | Crisp, auditable label assignment. |
| Natural language summary (C1) | `ml_engine/anomaly/summary.py` | **Template generation** | String formatting | Reproducible, factually grounded text. LLM would risk hallucination on numbers. |
| Anomaly clustering | `c3_engine/clustering.py` | **Graph algorithms** | Connected components over correlation graph | Mathematically precise grouping. |
| Prescription targets | `c3_engine/prescriptions.py` | **Business rule table** | (sector, metric) -> target delta | Grounded in verified operational levers; guarantees realistic targets. |
| Case retrieval | `c3_engine/case_matcher.py` | **Information retrieval** | Jaccard index similarity over context tags | Fast, deterministic, fully auditable. |
| Executive narrative | `c3_engine/narrative.py` | **LLM — Gemini 2.0 Flash** | Structured JSON output with schema enforcement | Optimal LLM task: synthesising complex multidimensional structured data into clear prose. Numbers come pre-computed; the LLM only writes. |

---

## LLM Usage Constraints

| Property | Value |
|---|---|
| Model | Gemini 2.0 Flash (configurable via `GEMINI_MODEL` env var) |
| Calls per analysis | Exactly 1 (or 0 in degraded mode) |
| Input to LLM | Structured JSON (anomalies, prescriptions, matched cases, company profile) |
| Output from LLM | Structured JSON validated against `Narrative` Pydantic schema |
| On failure | Silent degradation to deterministic-only mode; `degraded=True` in response |
| Token tracking | `EnrichedReport.metadata.llm_tokens_used` |

---

## Verification

To confirm LLM is not used in statistical calculations, run:

```bash
grep -r "genai" backend/core/       # Should return nothing
grep -r "genai" backend/api/api/    # Should return nothing
grep -r "genai" backend/enrichment/ # Should return only c3_engine/narrative.py
```
