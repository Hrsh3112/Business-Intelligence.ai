/**
 * The pipeline's method registry — which stage uses deterministic logic,
 * which uses statistics, and the single one that uses an LLM.
 *
 * SOURCE OF TRUTH: `docs/llm-vs-deterministic.md`. This file is the condensed,
 * user-facing view of that matrix — one row per pipeline phase rather than all
 * 17 rows. When the doc changes, change this too; when this changes, check the
 * doc. Two descriptions of the same pipeline that disagree is precisely the
 * problem the cross-team contract exists to prevent.
 *
 * Every claim below was verified against the source before being published:
 * `genai` is imported in exactly one module (`c3_engine/narrative.py`),
 * `case_matcher.py` does compute a Jaccard index, and `clustering.py` does
 * walk connected components. Do not add a row here on the strength of a
 * document alone — a method label shown to a judge is a claim we have to
 * defend.
 */

export type MethodKind = "deterministic" | "statistical" | "rules" | "template" | "ml" | "llm";

export interface MethodEntry {
  stage: string;
  owner: "Ingestion" | "Detection" | "Enrichment";
  kind: MethodKind;
  technique: string;
}

export const METHOD_KIND_LABEL: Record<MethodKind, string> = {
  deterministic: "Deterministic",
  statistical: "Statistical",
  rules: "Business rules",
  template: "Template",
  ml: "ML Model",
  llm: "LLM",
};

export const METHODS: MethodEntry[] = [
  {
    stage: "Input parsing & validation",
    owner: "Ingestion",
    kind: "deterministic",
    technique: "Pydantic v2 schema + regex normalisers; alias resolution against a fixed metric catalog",
  },
  {
    stage: "Unit & period validation",
    owner: "Ingestion",
    kind: "deterministic",
    technique: "Range checks plus a distributional fraction/percent check; gap interpolation under 4 periods",
  },
  {
    stage: "Baseline generation",
    owner: "Detection",
    kind: "ml",
    technique: "Holt-Winters ETS (statsmodels, trend=additive, damped) fitted on company history — sector-parametric fallback for < 6 periods",
  },
  {
    stage: "Deviation measurement",
    owner: "Detection",
    kind: "statistical",
    technique: "Z-score and percentile rank against the band-adjusted baseline",
  },
  {
    stage: "Noise filtering",
    owner: "Detection",
    kind: "deterministic",
    technique: "4-layer sieve: magnitude |z| ≥ 1.5, persistence ≥ 2 periods, correlation consistency, seasonality",
  },
  {
    stage: "L1b — Multivariate detection",
    owner: "Detection",
    kind: "ml",
    technique: "Isolation Forest (sklearn, contamination=0.1, unsupervised). Applied when ≥ 2 metrics and ≥ 8 periods available",
  },
  {
    stage: "Cross-metric correlation",
    owner: "Detection",
    kind: "statistical",
    technique: "Pearson coefficients from a fixed per-sector matrix, threshold |r| ≥ 0.5",
  },
  {
    stage: "Driver directionality",
    owner: "Detection",
    kind: "statistical",
    technique: "Granger causality test (statsmodels, max_lag=2, p<0.05) when ≥ 10 periods; heuristic fallback",
  },
  {
    stage: "Severity scoring",
    owner: "Detection",
    kind: "deterministic",
    technique: "Weighted linear combination over 5 components, 0–100, then exclusive band thresholds",
  },
  {
    stage: "Threshold recalibration",
    owner: "Detection",
    kind: "ml",
    technique: "Beta-Binomial Bayesian update (prior Beta(1,1)) per (sector, metric) from analyst feedback log",
  },
  {
    stage: "Abstention gate",
    owner: "Detection",
    kind: "deterministic",
    technique: "Discrete boundary check on periods and confidence — auditable and reproducible",
  },
  {
    stage: "Anomaly summary",
    owner: "Detection",
    kind: "template",
    technique: "String formatting over computed values — no model, so numbers cannot be hallucinated",
  },
  {
    stage: "Anomaly clustering",
    owner: "Enrichment",
    kind: "deterministic",
    technique: "Connected components over the correlation graph",
  },
  {
    stage: "Prescription targets",
    owner: "Enrichment",
    kind: "rules",
    technique: "(sector, metric) → target delta table, resolved against C1's band-adjusted baseline",
  },
  {
    stage: "Case retrieval",
    owner: "Enrichment",
    kind: "rules",
    technique: "Jaccard index over context tags — fast, deterministic, fully auditable",
  },
  // The one LLM row. Rendered separately and last, with live model and token
  // data from the response, so the claim is about THIS run, not a brochure.
  {
    stage: "Executive narrative",
    owner: "Enrichment",
    kind: "llm",
    technique: "Structured JSON in, schema-validated JSON out. Every number is pre-computed; the model only writes prose",
  },
];

export const DETERMINISTIC_STAGE_COUNT = METHODS.filter((m) => m.kind !== "llm").length;
