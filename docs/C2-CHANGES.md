# C2 Change Report — post-integration work

**Component:** C2 (API, parsing, orchestration, frontend)
**Base:** `458cf1d` "Initial commit" (the merged v1 of C1 + C2 + C3)
**Branch:** `c2-fixes` — **local only, not pushed**
**Scope of change:** 53 files, ~+3200 / −158
**Audience:** C1's and C3's owners and their AI agents. Written to be read cold.

> **Read §1 first.** Three items in this work are inert until C1's or C3's owner
> acts, and one shared-schema field was added that both should know about.
>
> **§11 maps every item in `docs/critique.md` to what was done** — start there
> if you are checking coverage rather than reading changes.

Everything below was verified by running it: `255 backend tests pass`,
`tsc --noEmit` clean, `eslint` clean, `next build` succeeds, and each API
behaviour was exercised against a live server. Where something is unverified or
deliberately incomplete, it says so.

---

## 1. ACTION REQUIRED BY OTHER COMPONENTS

### 1.1 C3 — persona-tailored narrative (**blocking a stated requirement**)

**What C2 did.** `CompanyInput.persona` now exists (see §3.1) and C2 delivers
the value all the way to C3's front door. `orchestration/pipeline.py` attaches
it to the `AnomalyReport` immediately before calling `enrich_report()`, so it
is readable as `anomaly_report.persona` (`"executive"` or `"analyst"`).

**What is still missing.** `c3_engine/narrative.py` builds a single prompt and
has no persona concept, so the value **arrives and is ignored**. Verified live:
an `analyst` run and an `executive` run return byte-identical narrative prose.

**What C3 must do.** Read `anomaly_report.persona` and vary the prompt —
different depth and register for an executive versus an analyst. No schema work
is needed on C3's side: `c3_engine/schemas.py`'s `AnomalyReport` already sets
`extra="allow"`, so the field survives the crossing today.

**Why it matters.** The Round 2 minimum expectations require *"at least two
personas receiving different insight narratives or recommended actions."*
Until C3 acts, the deck and demo may claim persona-tailored **views** (C2
delivers those — different fields, different depth, field-level entitlement)
but **must not** claim persona-tailored narratives.

### 1.2 C1 + C3 — alternative hypotheses under low confidence

**What C2 did.** Anomalies with `noise_confidence < 0.5` now render an explicit
caveat: *"Weak signal — treat it as a question, not a finding"*, plus what would
resolve it (more periods).

**What is still missing.** The problem statement asks for *competing
explanations* ("this could be seasonal compression OR early churn
acceleration"). Naming the rival hypothesis requires the correlation model (C1)
and the case base (C3). **C2 will not invent one** — stating an explanation the
system did not derive is precisely the failure the refusal mechanism exists to
prevent.

**What would unblock it.** Either component emitting candidate explanations in
a structured field; C2 will render whatever lands.

### 1.3 C1 — informational only, no action needed

`CompanyInput` gained an optional `persona` field (§3.1). **C1 is unaffected
and cannot break on it:** `ml_engine/models/input_schema.py::CompanyInput`
declares no `model_config`, so Pydantic v2's default `extra="ignore"` applies
and `orchestration/c1_adapter.py` drops the field before C1 sees it. This was
verified against C1's source and is pinned by a test
(`test_lineage.py::test_c1_adapter_drops_it_without_raising`) so that if C1
ever switches to `extra="forbid"`, it fails in CI rather than at the demo.

### 1.4 C3 — the action-recommendation fields (critique P1 #6)

**Not started by anyone.** The problem statement defines the action format as
`driver → controllable lever → action → expected impact → owner → confidence →
monitoring plan`. `Adjustment` currently has `action`, `rationale`, `priority`,
`target_value` and `delta` — so roughly three of seven.

**Why C2 did not do it.** `Adjustment` is produced by C3 and lives in the shared
schema. C2 does not add fields to models it does not populate, and inventing an
`owner` or a `monitoring_plan` in the rendering layer would be fabricating
content — the same rule that stops us inventing costs or hypotheses.

**What C3 would do:** add `controllable_lever`, `expected_impact`, `owner`,
`confidence`, `monitoring_plan` to `Adjustment`. Placeholder values are
acceptable per the critique ("CFO / Finance team", "Monitor monthly for 3
periods") provided they are visibly generic rather than presented as derived.

**What C2 will do once it lands:** mirror the fields and render them in
`PrescriptionCard.tsx`. Small, and it does not block anything else.

### 1.5 Open questions carried over (unchanged by this work)

| # | Question | Owner |
|---|---|---|
| 1 | `ActionItem` was renamed `action/priority/rationale` → `title/description/impact/effort` during integration. Was this agreed? The contract document still describes the old shape. | C3 |
| 2 | Is the widespread `extra="allow"` + defaulted-required-fields posture in `models/shared.py` permanent, or a merge-day expedient to tighten before submission? | All |
| 3 | `ReportMetadata.metrics_analyzed` is typed `Union[int, list[str]]`. Which does C1 actually emit? | C1 |
| 4 | Silently noise-filtered metrics still have no explanation channel (`metadata.filtered_metrics` was requested pre-integration). A user submits 8 metrics, sees 5, and C2 cannot say why. | C1 |

---

## 2. API surface

| Route | Status | Notes |
|---|---|---|
| `GET /health` | unchanged | |
| `POST /analyze` | changed | now also returns `source_manifest`, `cost`, `persona` |
| `POST /analyze/upload` | changed | as above; new `NO_USABLE_METRICS` outcome |
| `POST /validate` | unchanged | |
| **`POST /feedback`** | **NEW** | records a user verdict; append-only JSONL |
| **`GET /metrics/{sector_id}`** | **NEW** | canonical metric catalog for a sector |

### `POST /feedback`

```jsonc
// request
{ "job_id": "…", "target": "report|narrative|anomaly", "anomaly_id": null,
  "verdict": "useful|not_useful",
  "correction": "was_noise|severity_understated|severity_overstated|wrong_root_cause|null",
  "comment": "optional, max 2000 chars" }
// response
{ "recorded": true, "message": "Thanks — recorded." }
```

Appends one JSON line to `settings.FEEDBACK_LOG_PATH`, with a server-stamped
`received_at` (the client clock is not treated as evidence). An `OSError`
(full disk, read-only volume, bad path) degrades to `recorded: false` at
**HTTP 200** — never a 500.

**Scope honesty, please preserve it:** this is a log, not a learning loop.
Nothing reads the file back and no model retrains. The UI says "recorded", never
"we'll learn from this". Req 7 asks for a feedback mechanism and the defensible
claim is "captured, structured, from the first run" — the first hop of the
Living Knowledge Base, which remains roadmap.

### `GET /metrics/{sector_id}`

Returns every metric the system accepts for a sector: `metric_id`,
`display_name`, `unit`, `category`, `direction`, `valid_min`/`valid_max`, the
**accepted alias table**, and the min-period thresholds.

This is the machine-readable half of the KPI/semantic contract. It reads the
same `metric_config.yaml` the parser enforces, so what the API advertises and
what it accepts cannot drift — pinned by
`test_metrics_route.py::test_advertised_bounds_match_the_config_the_parser_enforces`.

Sector id is case-insensitive. An unknown sector returns a clean **404** naming
the valid ones — deliberately not an empty catalog, which would read as
"supported, you just have no metrics". `MFG` is out of MVP scope and 404s.

---

## 3. Schema changes

### 3.1 `api/models/shared.py` — ONE addition (cross-team, unsigned)

This is the **only** field C2 has ever added to the shared contract. It is
documented in place with a full docstring; the summary:

```python
class Persona(str, Enum):
    EXECUTIVE = "executive"
    ANALYST = "analyst"

class CompanyInput(BaseModel):
    ...
    persona: Optional[Persona] = None   # C2-PROPOSED, UNSIGNED
```

- **Why on the shared schema.** For persona to influence C3's narrative it must
  reach the C3 call. The only route that does not breach C2's architectural
  boundary (`run_pipeline()` takes a `CompanyInput` and nothing else) is to
  carry it inside the `CompanyInput`.
- **Why `Optional`, defaulting to `None`.** Absent means "not declared" (e.g. a
  direct `POST /analyze`), which is different from asserting a persona for every
  submission. C2's own UI default lives on `FormMetadata`, not here.
- **Semantic caveat.** It describes the reader, not the company, so it sits
  oddly on `CompanyInput`. It is there because it is the only
  boundary-respecting route, not because it is the tidiest home. If C1/C3
  prefer a different carrier, C2 will follow.

**No other shared model was touched.** `AnomalyReport`, `EnrichedReport`,
`MetricEntry`, `DeviationDetail` and everything else are byte-identical to the
integration baseline. Where C2 needed new fields, they went on C2-owned models
in `api/models/internal.py` instead — see §3.3 for the case where that was a
deliberate deviation from our own plan.

### 3.2 `api/models/internal.py` — new C2-owned models

| Model | Purpose |
|---|---|
| `CostEstimate` | LLM cost, derived not measured. `estimated_usd` is `None` — never `0.0` — when no rate is configured or no LLM ran. Carries a `basis` string so the figure can be defended. |
| `MetricSource` | Per-metric provenance: source, grain, freshness, coverage, gap-fill count, confidence. |
| `MetricCatalogEntry` / `MetricCatalogResponse` | `GET /metrics/{sector}` payload. |
| `FeedbackRequest` / `FeedbackResponse` | `POST /feedback` payload. |
| `FeedbackVerdict` / `FeedbackCorrection` | Enumerated verdicts and corrections. |
| `ErrorCode.NO_USABLE_METRICS` | New member — see §4.1. |

`ApiResponse` gained `cost`, `source_manifest`, and `persona`.
`FormMetadata` gained `persona`, `source_system`, and `metric_sources`.

### 3.3 Deviation worth recording: lineage did **not** need a schema change

Our own plan called for adding `source_system` / `data_as_of` to `MetricEntry`
in `shared.py`. We didn't. Everything the manifest needs — grain, period
coverage, interpolation counts, confidence — is *already* on `MetricEntry`, and
only the source label needed declaring, which went on `FormMetadata` (C2-owned).
Same user-visible result, zero risk to C1 and C3.

---

## 4. Behaviour changes

### 4.1 Empty-metrics submissions no longer blame C1 — **regression fixed**

**Before (integration baseline).** If every column was discarded during
validation (fraction-encoded percentages, short series, unrecognised headers),
C2 still sent `metrics: []` onward. `c1_adapter` raised, the orchestrator's
generic handler caught it, and the user saw
`status: "failed", error: "C1_FAILED"` — rendered as *"Something went wrong."*
C1 was blamed for a submission problem and the user learned nothing.

**After.** C2 blocks before dispatch:
- `parsing/builder.py` populates `blocking_errors` when nothing survives.
- `routes/analyze.py` returns `status: "failed"`, `error: "NO_USABLE_METRICS"`,
  with every per-column exclusion reason in `warnings`.
- `pipeline.py` catches `C1InputAdapterError` separately as a backstop for a
  hand-rolled `POST /analyze` body.
- The UI renders *"We couldn't use any of the data in your file"* followed by
  the reasons, instead of a generic error.

**C1 guarantee strengthened:** C2 will not send an empty `metrics` list.

### 4.2 Persona transport

`FormMetadata.persona` → `CompanyInput.persona` → **dropped by C1** →
re-attached by `pipeline.py` onto the `AnomalyReport` → visible to C3. Each hop
is pinned by a test, because a break anywhere is silent. See §1.1.

### 4.3 CORS default tightened

`allow_origins` moved from `["*"]` to `settings.cors_allow_origins`, defaulting
to `http://localhost:3000,http://127.0.0.1:3000` and overridable via
`CORS_ALLOW_ORIGINS`. Methods and headers narrowed to what the app uses.

**Note:** the previous setting was not merely permissive, it was quietly broken
— browsers reject `allow_origins="*"` combined with `allow_credentials=True`.

### 4.4 Smaller corrections

| Fix | Detail |
|---|---|
| Mock C3 copy | `f"A {a.severity_label} anomaly…"` rendered **"A SeverityLabel.SEVERE anomaly"** into user-facing narrative text. Needed `.value`. Was baked into the demo fixtures. |
| `web/src/types/api.ts` | Was stale — still declared the pre-integration `ActionItem`. Regenerated; the `as any` casts it had forced into `Narrative.tsx` are gone. |
| Scenario fixtures | All four were stale (old `ActionItem` shape). Regenerated. |
| `Highlights.tsx` | Called `.toFixed()` on `percentile`, which integration made nullable — a **runtime crash** whenever C1 omits it. |
| `Sparkline` | Required a `z_score` that integration made optional (and which it never reads). |
| `ResultsView` | Dereferenced `metadata.skipped_metrics` bare; `metadata` now has a server-side default. |
| `.env.example` | Named `NEXT_PUBLIC_API_URL`; the client reads `NEXT_PUBLIC_API_BASE_URL`. |
| `start.sh` / `start.ps1` | Now set `PYTHONPATH`, so a clean clone runs without `pip install -e backend` first. |
| `docs/llm-vs-deterministic.md` | Two verification commands were wrong: one pointed at `backend/api/api/` (does not exist) and one claimed a grep returns only `narrative.py` when it also returns the test and a `.pyc`. A judge running them would conclude the claim failed. |

> The three frontend crashes above were invisible until `types/api.ts` was
> regenerated. They are the concrete argument for keeping generated types in
> sync, and for treating open question §1.5 #2 (schema loosening) as real.

---

## 5. New files

### Backend

| Path | Purpose |
|---|---|
| `api/config/llm_pricing.yaml` | LLM rates. The only place a price lives. |
| `api/config/pricing.py` | `estimate_cost()`. Kept out of `pipeline.py` so the orchestrator still only routes, times and catches. |
| `api/parsing/lineage.py` | `build_source_manifest()` — derives provenance from the `CompanyInput` C2 already holds. |
| `api/routes/feedback.py` | `POST /feedback`. |
| `api/routes/metrics.py` | `GET /metrics/{sector_id}`. |
| `api/tests/test_pricing.py` | 11 tests. |
| `api/tests/test_feedback_route.py` | 9 tests. |
| `api/tests/test_lineage.py` | 17 tests (lineage + persona transport). |
| `api/tests/test_metrics_route.py` | 14 tests (catalog + CORS). |
| `data/samples/example_saas_multisource.csv` | Two-source demo input. |

### Frontend

| Path | Purpose |
|---|---|
| `components/TelemetryChip.tsx` | Latency, tokens, estimated cost. |
| `components/MethodPanel.tsx` | LLM vs non-LLM breakdown, LLM row rendered from live data. |
| `components/SourceManifestPanel.tsx` | Provenance table. |
| `components/FeedbackControl.tsx` | Thumbs up/down + structured correction. |
| `components/PersonaSwitcher.tsx` | Live persona view toggle + `EntitlementNote`. |
| `lib/methods.ts` | Method registry condensed from `docs/llm-vs-deterministic.md`. |
| `app/icon.svg` | Brand favicon, replacing the default Next.js one. |

**Deleted:** `web/src/app/favicon.ico` and the five unused create-next-app SVGs
in `web/public/`.

---

## 6. Configuration

New environment variables (all in `.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated. `"*"` still accepted, but now a deliberate choice. |

Clarified, not changed: `FEEDBACK_LOG_PATH` is relative to the **server's
working directory**. `start.sh` launches uvicorn from `backend/`, so the log
lands at `backend/feedback.jsonl`, not the repo root. It is gitignored.

`api/config/llm_pricing.yaml` is new config. It holds a **blended** rate per
model because C3 reports a single `llm_tokens_used` total rather than an
input/output split. If C3 ever splits the count, widen `estimate_cost()` to
match — the current shape is deliberately not final.

---

## 7. What we deliberately did NOT do

| Item | Why |
|---|---|
| **Touch any C1 or C3 source file** | Out of scope by instruction. Every change is in `backend/orchestrator/api/`, `web/`, `scripts/`, `docs/`, or root config. |
| **Tighten the schema loosening** in `models/shared.py` | Rejecting output that no one has inspected is riskier than accepting it. Needs a team decision — §1.5 #2. |
| **Push anything** | 4 commits sit on local branch `c2-fixes`. Nothing has reached the remote. |
| **Enforce persona entitlement server-side** | The redaction is presentation-layer. The payload still contains every field, and the UI says so verbatim: *"In production this would be enforced at the data layer with row- and column-level security; here the redaction is applied in the presentation layer only."* Calling conditional rendering "field-level security" is disprovable with devtools in ten seconds. |
| **Invent alternative hypotheses** | See §1.2. |
| **LLM response caching** | Listed as "needs a decision" and it still does. A cache keyed on the report hash would cut cost and latency, and a "cache hit · $0.00" chip demos well — but a re-run of the same CSV would then report zero tokens, which reads as a broken LLM unless explained, and it adds a staleness failure mode. Not adopted unilaterally. |
| **Claim a live second data source** | The manifest records *declared* provenance and computed grain/freshness. It is lineage and labelling, not a connector, and is described that way. |

### The honesty rules applied throughout

Three rules governed every user-facing number added in this work, and they are
worth preserving in future changes:

1. **Never invent a number.** Cost is `None`, never `0.0`, when unknown. An
   unpriced model reports *"no published rate configured"*.
2. **Computed and declared must not look alike.** Grain, coverage, freshness and
   gap-fill counts are measured; `source_system` is a user claim or a filename.
   `MetricSource.source_basis` records which — `declared`, `upload_filename`,
   or `unknown`.
3. **Label estimates as estimates.** The cost chip reads `~$0.000077 est.` and
   carries its derivation basis on hover.

---

## 8. Known issues and gotchas

| Issue | Detail |
|---|---|
| **uvicorn `--reload` is unreliable here** | It once served a **new Pydantic model with an old route**, producing an empty field rather than an error — cost ~20 minutes chasing a non-bug. **After backend edits, restart the server rather than trusting reload.** |
| **One intermittent test** | `test_analyze_route.py::test_valid_body_returns_200_complete` failed twice, both times on runs 4–13× slower than normal (cold start; immediately after a `next build` saturated the disk). Not reproducible in ~10 subsequent runs. Almost certainly a timeout under load. The assertion now prints `error=` and `timings=` so the next occurrence identifies itself instead of just saying "not complete". |
| **Degraded runs report no cost** | When the LLM fails, tokens are `None`, so no cost is claimed. Correct, but means the degraded scenario's telemetry chip shows latency only. |
| **`AMBIGUOUS_SHAPE` / `C1_UNAVAILABLE`** | Pre-existing dead enum members, untouched. |
| **`LLM_TIMEOUT_S`** | Pre-existing setting, still read by nothing. |

---

## 9. Running and verifying

```bash
# Backend (from repo root). Restart rather than relying on --reload.
cd backend
PYTHONPATH="core:enrichment:orchestrator" python -m uvicorn api.main:app --port 8000
#   Windows PowerShell: $env:PYTHONPATH='core;enrichment;orchestrator'
# …or `pip install -e backend` once, then plain uvicorn. start.sh/start.ps1 do
# the PYTHONPATH form for you.

# Tests — 255, all passing
cd backend && python -m pytest orchestrator/api/tests -q

# Frontend
cd web && npm ci && npm run dev          # needs the backend up
cd web && npx tsc --noEmit && npx eslint src && npm run build

# Regenerate artifacts after any backend model change — BOTH are checked in
# and BOTH go stale silently:
cd web && npm run types                                  # needs backend running
PYTHONPATH="backend/core:backend/enrichment:backend/orchestrator" \
  python scripts/dump_scenario_responses.py
```

> `scripts/dump_scenario_responses.py` bypasses `run_pipeline()`, so anything
> the pipeline derives must be derived there too or the offline demo silently
> loses it. This already happened once with `cost`. It now calls the same
> `estimate_cost()` and `build_source_manifest()` the pipeline calls.

### Quick smoke checks

```bash
curl -s localhost:8000/metrics/TECH_SAAS | head -c 300     # 7 metrics + aliases
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/metrics/MFG   # 404
curl -s -X POST localhost:8000/feedback -H 'Content-Type: application/json' \
     -d '{"job_id":"smoke","verdict":"useful"}'            # {"recorded":true,…}
```

---

## 10. Test inventory

| Suite | Count | Covers |
|---|---|---|
| Pre-existing | 199 | Parsing, validation, orchestration, degradation, mocks, routes |
| `test_pricing.py` | 11 | Cost arithmetic and every "we cannot stand behind a figure" branch |
| `test_feedback_route.py` | 9 | Recording, rejection, unwritable-path degradation |
| `test_lineage.py` | 17 | Computed vs declared provenance; persona transport, hop by hop |
| `test_metrics_route.py` | 14 | Catalog correctness, config equivalence, CORS |
| Added to existing files | 5 | `NO_USABLE_METRICS` paths |
| **Total** | **255** | |

---

## 11. Critique traceability

Maps every actionable item in `docs/critique.md` to what C2 did.

**Legend:** ✅ done · ◐ partial, with what's missing named · ⬜ not started ·
⚠️ unchanged by this work.

Statuses are C2's own honest reading, not a score to quote. Where an item is
partial, the deck should claim the delivered half and nothing more.

### Part 4 — prioritised fixes

| # | Critique item | What C2 did | Status | Still needed |
|---|---|---|---|---|
| **P0 1** | Add a persona selector | `Persona` enum, form selector, live in-place view toggle, field-level entitlement, and transport all the way to C3 | ◐ | **C3** must read `anomaly_report.persona` and vary the prompt — §1.1 |
| **P0 2** | Second data source; `source_system`/`data_as_of`; render on the card | `ApiResponse.source_manifest`; `FormMetadata.source_system` + per-metric `metric_sources`; source, grain, freshness, coverage and gap-fill count per metric, rendered on each card and in a panel; two-source sample CSV | ◐ | This is lineage and labelling, **not a live connector**. A real second datasource is out of MVP scope and should not be claimed |
| **P0 3** | Show LLM vs non-LLM breakdown in the UI | `MethodPanel` — 12 deterministic stages vs exactly 1 LLM call, LLM row rendered from live run data; per-anomaly provenance line | ✅ | — |
| **P0 4** | Show cost + latency telemetry in the UI | `TelemetryChip` — total/C1/C3 latency, token count, estimated cost with its derivation basis | ✅ | — |
| **P1 5** | Add a feedback button | `POST /feedback` (JSONL, degrades to `recorded:false`, never 500) + `FeedbackControl` on the narrative and every anomaly, with enumerated corrections | ✅ | Nothing reads the log back — deliberate, and stated in the UI copy |
| **P1 6** | `owner` + `monitoring_plan` on `Adjustment` | Nothing | ⬜ | **C3** owns the schema and the values — §1.4 |
| **P1 7** | Root README, one-command start, remove internal docs | Already done by C1 at integration. C2 fixed `start.sh`/`start.ps1` to set `PYTHONPATH` so a clean clone runs without `pip install -e backend` | ✅ | — |
| **P1 8** | Role-based security / entitlement demo | Statistical fields withheld from the executive view, with an explicit on-screen note that this is presentation-layer redaction, not enforcement | ✅ | Real row/column security belongs at the data layer; out of MVP scope |
| **P2 9** | Source freshness on anomaly cards | Source, grain, as-of period, point count and gap-fill count on each card | ✅ | — |
| **P2 10** | Alternative hypothesis under low confidence | Weak-signal caveat below `noise_confidence < 0.5`, naming what would resolve it | ◐ | **C1/C3** must emit the competing explanations — §1.2 |
| **P2 11** | Frontend title and favicon | Title was already correct; brand `icon.svg` replaces the Next.js default; five unused create-next-app SVGs removed | ✅ | — |
| **P2 12** | Health score as a gauge / coloured indicator | Meter beside the number plus a band label; **no bar at all on refusal**, since a grey track beside "N/A" reads as "scored, and bad" | ✅ | — |

### Part 3 — minimum prototype expectations

| Expectation | Critique | Now | Note |
|---|---|---|---|
| 3–5 KPIs across 2–3 sources, different grains | ❌ | ◐ | Per-metric source and grain in the manifest; two declared systems demoable. Still a single upload |
| Lightweight KPI/semantic contract | ⚠️ | ✅ | `GET /metrics/{sector_id}` serves it at runtime from the same YAML the parser enforces |
| ≥2 personas, different narratives or actions | ❌ | ◐ | Different **views** delivered; different **narratives** blocked on C3 |
| One multi-factor KPI movement with known drivers | ⚠️ | ⚠️ | Unchanged — driver attribution is C1/C3 |
| One low-confidence scenario with abstention | ✅ | ✅ | Strengthened: `NO_USABLE_METRICS` plus the weak-signal caveat |
| Sparse-history / newly launched KPI scenario | ⚠️ | ⚠️ | Short-series warnings exist; still not a distinct named demo scenario |
| Role-based security / entitlement scenario | ❌ | ✅ | Demo-level, honestly labelled |
| Evidence: freshness, method, contribution, confidence, lineage | ❌ | ◐ | freshness ✅ · method ✅ · confidence ✅ · lineage ✅ · **contribution ❌** |
| Clear LLM vs non-LLM breakdown | ⚠️ | ✅ | `MethodPanel`; also corrected two wrong verification commands in `llm-vs-deterministic.md` |
| Runtime telemetry: latency, model calls, tokens, cost | ⚠️ | ✅ | `TelemetryChip` |

Movement on these ten rows: **2✅ / 5⚠️ / 3❌ → 5✅ / 3◐ / 2⚠️ / 0❌.**

The one hard gap that remains is **contribution / driver attribution** — which
of several correlated anomalies is the driver and which are symptoms. That is
C1 and C3's, and it is the deepest requirement still unmet.

### Part 2 — requirement level

| Req | After this work | Remainder owned by |
|---|---|---|
| 1 — Detect and prioritise material movements | Unchanged | C1 (business-impact materiality, decision urgency) |
| 2 — Reconcile heterogeneous sources | Lineage, grain and freshness now surfaced | Real multi-source ingestion — out of MVP scope |
| 3 — Identify and rank explanatory drivers | Unchanged; method labels now visible | **C1/C3 — the biggest remaining gap** |
| 4 — Persona narratives with traceable evidence | Evidence chain substantially improved (manifest + method panel + telemetry + per-card provenance) | C3 for persona-varied prose — §1.1 |
| 5 — Communicate uncertainty, abstain | Strengthened | — |
| 6 — Practical actions grounded in levers | Unchanged | C3 — §1.4 |
| 7 — Learn from feedback | Capture mechanism now exists | Nothing consumes the log yet (roadmap, stated) |
| 8 — Security, cost, latency, scalability | Telemetry ✅, CORS tightened ✅ | Auth, rate limiting, row/column security, LLM caching — none attempted |

### Not attempted, on purpose

`docs/critique.md` Part 5's core charge — that the system is a *peer-benchmark
health checker* rather than a *KPI intelligence-to-action engine* — is an
architectural criticism of C1's detection model, not something C2 can close from
the API and rendering layer. It is recorded here so nobody assumes it was
addressed.
