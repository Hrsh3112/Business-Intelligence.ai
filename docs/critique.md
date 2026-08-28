# Critical Review — businessintelligence.ai vs. Round 2 Problem Statement

> No punches pulled. This is a pre-submission triage document.

---

## Part 1 — Directory Structure & Presentation

### What You Have

```
Accenture/
├── ml_engine/          ← C1: anomaly detection (Python package)
├── API-Setup/
│   ├── api/            ← C2: FastAPI backend
│   └── web/            ← Frontend: Next.js
├── LLM-Case-Based/
│   └── c3_engine/      ← C3: prescriptions + case match + narrative
├── Docs/               ← One .pptx + one .md
├── testing/            ← One test CSV
└── README.md
```

### Problems

#### 1. The top-level README is for `ml_engine` only — the project doesn't have an entry point
The root `README.md` is entirely about C1 (`ml_engine`). There is no document at the root that tells a judge:
- What this thing actually does end-to-end.
- How to run the full stack locally (start API, start frontend, run demo).
- Which demo scenarios exist and how to trigger them.
- What the architecture diagram is at the system level.

A judge opening this repo has to spelunk three different sub-directories to understand the system. That is a failure of presentation.

#### 2. `Docs/` is nearly empty
`Docs/Intro.pptx` is 5.5 MB and `api-integration-notes.md` is 11 KB. There is no:
- System architecture diagram (not in a `.md`, not as a `mermaid`, not as an image).
- KPI semantic contract document in a readable format.
- Persona definition document.
- LLM vs. non-LLM breakdown document.

The problem statement explicitly asks for **evidence showing source freshness, analytical method, contribution, confidence and lineage** and **a clear breakdown of LLM versus non-LLM processing**. These need to be discoverable artifacts, not buried in a 40 KB `C2-MasterPlan.md` that reads like internal team notes.

#### 3. Internal planning documents are in the submission repo
`C2-MasterPlan.md`, `CLAUDE.md`, `AGENTS.md`, and `pipeline-Contract-V1.md` are checked into the API-Setup directory. These are internal build notes and team handshake documents. They should not be in what a judge sees. They signal that the team submitted a work-in-progress working directory rather than a curated deliverable.

#### 4. Three separate Python packages with no unified entry point
`ml_engine`, `c3_engine`, and `api` are three separate installable packages across two different directories. There is no `docker-compose.yml`, no `Makefile`, no root-level `start.sh` or setup script that brings everything up in one command. On demo day, if someone asks "can I run this?" the answer is currently "follow three READMEs across two directories and hope the import paths line up."

#### 5. `testing/` is a graveyard
One file: `test-1.csv` (186 bytes). This directory communicates either that testing was abandoned or that it's a forgotten artifact. Either way, it undermines confidence.

#### 6. No visual identity / branding on the frontend
The frontend is typographically clean (good), but it looks like a developer prototype. For a competition pitch:
- There is no logo, no product name displayed prominently, no favicon that is the actual brand (currently just the default Next.js icon).
- The `layout.tsx` title is the browser default. The page title a judge sees in their browser tab communicates nothing.
- The color scheme (`ink`, `ground`, `rule`, `accent`, `flag`) is minimal/monochrome. It passes accessibility but it doesn't *demo* well under projector lights or screenshots.

---

## Part 2 — Logic vs. the Problem Statement

I'll go requirement by requirement.

---

### Req 1: Detect and prioritise material KPI movements ✅ (partial)

**What you have:** A solid 4-layer sieve (z-score cutoff → persistence → cross-metric correlation → contextual filter) with severity scoring and exclusive bands (INFO/WARNING/CRITICAL/SEVERE). The `overall_health_score` is weighted by metric weights. This is **genuinely good** and deterministic, which is exactly what the judges want.

**What is missing:**

- **Materiality based on business impact is absent.** The severity score is entirely statistical (z-score, percentile, slope, acceleration). The problem statement says materiality must be assessed on *both* statistical significance *and* business impact. A −0.3% gross margin swing in a VC-backed company burning \$500K/month is materially different from the same swing in a profitable SME. There is no dollar/impact weighting — the system cannot distinguish "interesting anomaly" from "company-killing anomaly."
- **Prioritisation is just sorting by `severity_score` descending.** There is no concept of decision-urgency, time-to-impact, or reversibility. A fast-accelerating deteriorating metric should be surfaced differently than a stable one that is simply below baseline.

---

### Req 2: Reconcile data and business context across heterogeneous sources ❌ (missing)

**What you have:** A CSV upload from a single source. One grain. One refresh cadence. One file.

**What is entirely missing:**

- **Multiple data sources.** The minimum prototype expectation is *"three to five connected KPIs across two or three data sources with different grains or refresh cadences."* You have one source (a user-uploaded CSV). There is no database connector, no second datasource, no refresh cadence metadata, no data freshness indicator anywhere in the pipeline.
- **Source freshness.** The problem statement explicitly requires evidence showing "source freshness." The `AnomalyReport` schema has no `data_as_of`, no `source_system`, no `last_refreshed` field.
- **Heterogeneous grain reconciliation.** Monthly vs. weekly vs. quarterly data is not handled. The `PeriodType` enum exists but the pipeline does not upscale or downscale between grains.
- **Data quality levels.** `confidence` is on the `MetricInput`, which is good, but it's a user-provided float with no validation against actual data quality signals. There is no missing-data imputation logic that is visible or documented.

This is arguably the biggest gap relative to the stated requirements.

---

### Req 3: Identify and rank explanatory drivers using appropriate analytical methods ⚠️ (weak)

**What you have:** Cross-metric correlation in the noise filter (`CorrelationEngine`) and anomaly clustering in C3 (`build_anomaly_clusters`). The correlation engine links anomaly IDs. Clustering groups related anomalies.

**What is missing:**

- **Driver ranking with attribution.** The system detects *that* multiple metrics are anomalous together and *that* they're correlated. It does not explain *which one is the driver and which ones are symptoms.* There is no contribution analysis, no variance decomposition, no "MRR growth declined 4.2pp, of which 2.1pp is attributable to increased churn and 1.8pp to CAC inflation" style output.
- **Causal direction is absent.** The correlation engine is symmetric. The problem statement explicitly calls out causal inference as an approach. You have correlation, not causation.
- **No price/volume/mix decomposition.** The problem statement specifically lists "price, volume, mix, marketing, supply, seasonality, competition and external events" as interacting drivers. None of these decompositions exist.
- **The analytical methods used are not surfaced to the user.** The judges want to see you demonstrate *when you use deterministic logic vs. SQL vs. statistics vs. ML vs. LLM — and why.* There is no method label on any anomaly card, no "how we detected this" trace, no lineage shown in the UI.

---

### Req 4: Generate persona-specific narratives supported by traceable evidence ❌ (missing)

**What you have:** One narrative generated by Gemini, same for all users. The `Narrative` schema has `situation_summary`, `likely_root_causes`, `prioritized_actions`, `positives`. These are well-structured.

**What is entirely missing:**

- **Personas.** The minimum prototype expectation is *"at least two personas receiving different insight narratives or recommended actions."* There is zero persona concept in the codebase. There is no role field in the input, no persona-specific prompt variation, no different depth of narrative for a CFO vs. an operations analyst.
- **Traceable evidence.** The narrative produced by the LLM contains no citations, no references back to specific data points. The problem statement says "supported by traceable evidence." The LLM prompt dumps data into context but the output `Narrative` schema has no `evidence` or `citations` field. The UI renders the narrative as plain paragraphs with no link back to the anomaly cards.
- **The evidence chain is broken.** An anomaly card shows `observed`, `expected`, `delta` — but there is no lineage showing *which synthetic baseline version* was used, *which data source* contributed the observed value, or *what time period* the expected value was calibrated on.

---

### Req 5: Communicate uncertainty and abstain when evidence is insufficient ✅ (strong)

**What you have:** The refusal mechanism is the best-implemented feature in this project. The 4-layer noise filter, `noise_confidence` field on anomalies, `RefusalDetail` schema, `RefusalView` component, and the explicit "not enough evidence" messaging are all thoughtfully done. The `contradictory_evidence` refusal reason is defined. The degraded-mode cascade (LLM fails → system still returns C1 results) is correctly architected.

**What is missing (small gaps):**

- **Confidence scores are not shown to the user with their meaning explained.** The `SeverityConfidenceBar` renders two bars but the labels are small. A judge wants to see "this anomaly has noise_confidence=0.82 because it passed 3 of 4 filter layers" — not just a bar.
- **Alternative hypotheses.** The problem statement asks for "alternative hypotheses" in the low-confidence scenario. Currently refusal is binary: either you get a narrative or you get a refusal. There's no "here are two competing explanations for this movement, we can't choose between them."
- **The "contradictory evidence" refusal is defined but not triggered.** There is no path in the detector that sets `refusal.reason = "contradictory_evidence"` based on actual signal conflict. It's dead code.

---

### Req 6: Recommend practical actions grounded in business levers, constraints and decision rights ⚠️ (weak)

**What you have:** The `prescriptions.py` rule table is deterministic and explicit (which is good). It maps `(sector, metric)` → `(action, rationale, priority)`. The `Adjustment` schema has `current_value`, `target_value`, `delta`, `priority`, `rationale`, `target_basis`.

**What is missing:**

- **The required action structure.** The problem statement defines the action recommendation format as: `driver → controllable lever → action → expected impact → owner → confidence → monitoring plan`. Your `Adjustment` has `action` and `rationale` but is missing: `controllable lever` (what business knob to turn, not just the metric), `expected impact` (quantified, e.g. "reducing CAC by 15% would extend runway by 2 months"), `owner` (who in the org is responsible), `confidence` (how likely is this to work), and `monitoring plan` (what to track, at what cadence, to confirm it's working).
- **Business constraints are absent.** Prescriptions assume the target is always the synthetic baseline. There is no constraint reasoning ("you can't increase headcount because burn_rate is already SEVERE") or dependency ("fix churn before CAC, because CAC ROI depends on LTV which depends on churn").
- **Decision rights are not modelled.** A CFO cannot recommend a product change; an ops lead cannot authorize a capital raise. There is no ownership or authorization layer on any action.
- **The rule table is static and hand-coded.** For only 2 sectors × 7-8 metrics, it works. But it communicates that the system cannot generalize. The judges will ask "what happens with a metric you haven't hardcoded?"

---

### Req 7: Mechanism to learn from analyst and business-user feedback ❌ (missing)

**What you have:** Nothing. There is no feedback mechanism anywhere in the codebase. Zero.

**What is missing:**
- No thumbs up/down on narrative or anomaly cards.
- No "was this useful?" prompt.
- No feedback storage (even a local JSON file would show intent).
- No mechanism for an analyst to say "this was noise, suppress it" or "this was more severe than the score suggests."
- No correction workflow ("the LLM said X but the real cause was Y").
- No learning loop, no feedback table, no drift detection.

This is a complete blind spot. Even a fake UI stub with a "Submit feedback" button and a local log would be better than nothing.

---

### Req 8: Operate within realistic security, cost, latency and scalability constraints ⚠️ (partially addressed)

**What you have:**
- `Timings` schema captures `c1_ms`, `c3_ms`, `total_ms`. Token usage is captured in `EnrichmentMetadata` (`llm_tokens_used`, `llm_model`). This is real telemetry and it's good.
- Degraded mode means the system stays up when the LLM is unavailable.
- Timeout handling for both C1 and C3 with explicit logging.

**What is missing:**

- **Cost per insight is not computed or displayed.** Token count is captured but there is no `estimated_cost_usd` field. The UI shows no telemetry at all — no "this analysis took 320ms, used 1,200 tokens (~\$0.0003)" summary visible to the user or judge.
- **Security is completely open.** `allow_origins=["*"]` is flagged in the code as something to tighten, but it never was. There is no authentication, no API key validation, no rate limiting, no row/column/domain-level security. The problem statement explicitly asks for "row-, column- and domain-level security, sensitive-data protection and auditability." You have none of this.
- **Role-based security or entitlement scenario** is listed as a minimum prototype expectation. There is no user identity concept anywhere.
- **No caching.** The same CompanyInput submitted twice will call Gemini twice. There is no request-level cache on the LLM call despite the token cost concern.
- **Scalability.** The pipeline is synchronous in a thread (`asyncio.to_thread`). The comments in the code acknowledge this is a known limitation for MVP. That's fine, but the judges need to see you've *thought about* what the production architecture would look like (a process pool, a task queue, etc.).

---

## Part 3 — Minimum Prototype Expectations Checklist

| Expectation | Status | Notes |
|---|---|---|
| 3–5 connected KPIs across 2–3 data sources with different grains | ❌ | One source (CSV upload). No multi-source. |
| Lightweight KPI/semantic contract | ⚠️ | `pipeline-Contract-V1.md` exists but isn't a runtime artifact — it's a planning doc. No machine-readable KPI contract. |
| At least 2 personas, different narratives/actions | ❌ | No persona concept exists. |
| One multi-factor KPI movement with known drivers | ⚠️ | Demo scenarios exist but driver attribution is not explicit. |
| One low-confidence scenario with clarification/abstention | ✅ | Refusal scenario exists and works. |
| One sparse-history / newly launched KPI scenario | ⚠️ | Refusal fires for < 6 periods, but "sparse history" is not a distinct scenario separate from "insufficient periods." |
| One role-based security / entitlement scenario | ❌ | Does not exist. |
| Evidence: source freshness, analytical method, contribution, confidence, lineage | ❌ | Not surfaced anywhere in the UI or output schema. |
| Clear breakdown of LLM vs. non-LLM processing | ⚠️ | Implicit (C1 = deterministic, C3 narrative = LLM) but not shown to the user. |
| Runtime telemetry: latency, model calls, token usage, estimated cost | ⚠️ | Latency and token count captured; not shown in UI; cost not computed. |

**Score: 2 full ✅, 5 partial ⚠️, 3 missing ❌**

---

## Part 4 — What to Actually Fix Before Submission (Prioritised)

### P0 — Showstoppers (will cost you the demo)

1. **Add a persona selector.** Even two personas (CEO and COO) with different LLM prompt templates producing different narrative depth. This is a minimum expectation and you have zero. It requires: a persona field on the input form → passed through to the narrative prompt → different `situation_summary` depth.

2. **Add a second data source, even simulated.** Label two of your metrics as coming from "CRM system (daily)" and the rest as coming from "ERP system (monthly)." Add `source_system` and `data_as_of` to the `MetricInput` schema and render it on the anomaly card. This directly addresses Req 2 and the multi-source expectation.

3. **Show the LLM vs. non-LLM breakdown in the UI.** Add a small "How we did this" footer or modal that says: "Anomaly detection: deterministic (z-score, 4-layer sieve) | Driver attribution: Pearson correlation | Narrative: Gemini 2.0 Flash (1,200 tokens, ~\$0.0003) | Case matching: Jaccard similarity on tag overlap." This addresses Req 3, Req 8, and the explicit judging criterion.

4. **Show cost + latency telemetry in the UI.** Add a small bottom-right chip: "Analysis complete in 1.2s · 1,400 tokens · ~\$0.0004." The data is already in the `Timings` and `EnrichmentMetadata` objects. You just need to surface it.

### P1 — High Impact, Achievable

5. **Add a feedback button.** Even a stub that logs to a local file. The problem statement requires it. A thumbs-up/thumbs-down on the narrative card that posts to `/feedback` and appends to `feedback.jsonl` takes two hours and signals you've thought about the learning loop.

6. **Add `owner` and `monitoring_plan` fields to `Adjustment`.** The problem statement defines the action format explicitly: `driver → lever → action → impact → owner → confidence → monitoring plan`. You're missing four of seven fields. Add placeholder values ("CFO/Finance team", "Monitor monthly for 3 periods") so the schema is complete even if the values are defaults.

7. **Create a root-level `README.md` that explains the full system** and a `docker-compose.yml` or `start.sh` that runs everything. Remove `C2-MasterPlan.md`, `CLAUDE.md`, and `AGENTS.md` from the submission (or move them to a `.internal/` directory).

8. **Add a "Role-based security" demo scenario.** Even a conceptual demo: if the `persona` field is "analyst", certain fields (e.g. `z_score`, `noise_confidence`) are shown; if it's "executive", they're hidden. Pair this with a note in the UI: "Row-level security would be enforced at the data layer; field-level redaction is applied here based on persona entitlement."

### P2 — Nice to Have

9. **Add source freshness labels to anomaly cards.** Even static: "Source: CRM (as of 2026-08-27) | Grain: Monthly" renders next to the metric name.

10. **Add an "alternative hypothesis" to the low-confidence scenario.** When `noise_confidence < 0.5`, show two competing explanations ("This could be seasonal compression OR early churn acceleration — we need another 2 periods to distinguish.").

11. **Change the frontend title and favicon** to something that doesn't say "Create Next App."

12. **Replace the health score number with a gauge or colored indicator.** A large grey number on a white background does not demo well on a projector. Even a simple color band (green/amber/red) makes it immediately readable under presentation conditions.

---

## Part 5 — The Biggest Conceptual Misalignment

The system as built is a **company health checker benchmarked against synthetic peers**. You upload your metrics, we tell you which ones are anomalous compared to "a healthy SaaS company at your revenue band."

The problem statement is asking for a **KPI intelligence-to-action engine** that explains movements in KPIs over time, across multiple heterogeneous data sources, for different personas.

These are related but different problems. Your system excels at the "are you healthy compared to peers?" question. It is weak at the "why did revenue drop 12% this month and what should I do about it?" question — which is the actual Round 2 ask.

The mismatch shows up most clearly in: no multi-source data, no driver decomposition, no persona-specific depth, and no lineage/evidence chain from the narrative back to the data.

You have solid engineering. The C1/C2/C3 architecture, the degraded mode cascade, the noise filter, and the refusal mechanism are all genuinely well-thought-out. The gap is in scope coverage relative to what was asked, and in the presentation layer that lets judges understand what you built.
