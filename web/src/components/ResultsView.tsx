"use client";

import { useState } from "react";
import type { ApiResponse, Persona } from "@/lib/api";
import type { components } from "@/types/api";
import { HealthScore } from "./HealthScore";
import { DegradedBanner } from "./DegradedBanner";
import { Narrative } from "./Narrative";
import { AnomalyCard } from "./AnomalyCard";
import { PrescriptionCard } from "./PrescriptionCard";
import { MatchedCases } from "./MatchedCases";
import { Highlights } from "./Highlights";
import { SkippedMetricsNotice } from "./SkippedMetricsNotice";
import { ParseWarningsNotice } from "./ParseWarningsNotice";
import { RefusalView } from "./RefusalView";
import { TelemetryChip } from "./TelemetryChip";
import { MethodPanel } from "./MethodPanel";
import { FeedbackControl } from "./FeedbackControl";
import { SourceManifestPanel } from "./SourceManifestPanel";
import { PersonaSwitcher, EntitlementNote } from "./PersonaSwitcher";

interface ResultsViewProps {
  response: ApiResponse;
  onReset: () => void;
}

/**
 * Top to bottom (Phase3-Plan T3.3): health score -> degraded banner
 * (conditional) -> narrative -> anomalies -> highlights -> skipped-metrics
 * notice. A report you read top to bottom, not a grid dashboard.
 */
function ContributionWaterfall({ anomalies }: { anomalies: components["schemas"]["Anomaly"][] }) {
  const anomaliesWithContrib = anomalies.filter(
    (a) => a.contribution_pct !== null && a.contribution_pct !== undefined && a.contribution_pct > 0
  );
  if (anomaliesWithContrib.length === 0) return null;

  const colors = ["bg-accent", "bg-amber-600", "bg-indigo-600", "bg-teal-600", "bg-rose-600"];

  return (
    <div className="rounded-sm border border-rule bg-white/40 p-4">
      <div className="flex items-center justify-between text-xs font-medium tracking-wide text-ink-muted uppercase">
        <span>Variance / Health Drop Attribution</span>
        <span className="normal-case text-ink-muted">Multi-factor decomposition</span>
      </div>
      <div className="mt-2.5 flex h-3.5 w-full overflow-hidden rounded-full bg-rule/80">
        {anomaliesWithContrib.map((a, idx) => {
          const pct = Math.min(100, Math.max(0, a.contribution_pct ?? 0));
          const colorClass = colors[idx % colors.length];
          return (
            <div
              key={a.anomaly_id}
              className={`h-full ${colorClass} transition-all duration-300`}
              style={{ width: `${pct}%` }}
              title={`${a.metric_display_name}: ${pct.toFixed(1)}% of deterioration`}
            />
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-muted">
        {anomaliesWithContrib.map((a, idx) => {
          const colorClass = colors[idx % colors.length];
          return (
            <div key={a.anomaly_id} className="flex items-center gap-1.5">
              <span className={`h-2.5 w-2.5 rounded-full ${colorClass}`} />
              <span className="text-ink font-medium">{a.metric_display_name}</span>
              <span className="data text-ink-muted">({(a.contribution_pct ?? 0).toFixed(1)}%)</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ResultsView({ response, onReset }: ResultsViewProps) {
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  // Seeded from what the submission asked for, then switchable in place — the
  // two views are of one computed report, and toggling shows exactly that.
  const [persona, setPersona] = useState<Persona>(response.persona);

  if (!response.result) {
    // status: "failed" — nothing to render. NO_USABLE_METRICS is not a system
    // error: C2 read the file, discarded every column, and knows exactly why.
    // Showing "something went wrong" there would hide the one thing the user
    // needs, so the per-column reasons carried in `warnings` lead instead.
    const noUsableMetrics = response.error === "NO_USABLE_METRICS";
    return (
      <section className="mx-auto max-w-prose space-y-6 py-8">
        <div>
          <p className="text-xs font-medium tracking-wide text-ink-muted uppercase">Health score: N/A</p>
          <h2 className="font-display mt-2 text-2xl font-medium text-ink">
            {noUsableMetrics
              ? "We couldn't use any of the data in your file."
              : "We couldn't complete this analysis."}
          </h2>
        </div>

        <p className="text-base leading-relaxed text-ink">
          {noUsableMetrics
            ? "Every column was either unrecognised or excluded during validation, so there was nothing left to analyse. We'd rather tell you that than guess."
            : `The analysis stopped before it could produce a result${response.error ? ` (${response.error})` : ""}.`}
        </p>

        {response.warnings.length > 0 && (
          <div className="rounded-sm border border-rule bg-white/40 p-4">
            <p className="text-xs font-medium tracking-wide text-ink-muted uppercase">What we saw in your file</p>
            <ul className="mt-2 space-y-1.5">
              {response.warnings.map((warning, i) => (
                <li key={i} className="text-sm leading-relaxed text-ink-muted">
                  {warning.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <button
          type="button"
          onClick={onReset}
          className="rounded-sm border border-ink bg-ink px-4 py-2 text-sm font-medium text-ground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Try another file
        </button>

        <TelemetryChip response={response} />
      </section>
    );
  }

  const { anomaly_report, prescriptions, matched_cases, narrative, metadata } = response.result;

  if (response.status === "refused" && anomaly_report.refusal) {
    return (
      <>
        <RefusalView refusal={anomaly_report.refusal} warnings={response.warnings} onReset={onReset} />
        {/* Shown on the refusal path too: it is the one screen where the
            telemetry proves a claim — abstaining made no LLM call, and the
            method panel says so in its own LLM row. */}
        <div className="mx-auto max-w-prose space-y-4 pb-8">
          <TelemetryChip response={response} />
          <MethodPanel response={response} />
        </div>
      </>
    );
  }

  const sortedAnomalies = [...anomaly_report.anomalies].sort((a, b) => b.severity_score - a.severity_score);
  const prescriptionsByAnomalyId = new Map(prescriptions.map((p) => [p.anomaly_id, p]));
  const sourceByMetricId = new Map(response.source_manifest.map((s) => [s.metric_id, s]));

  return (
    <div className="mx-auto max-w-[880px] space-y-10 py-8">
      <header className="space-y-4">
        <PersonaSwitcher persona={persona} onChange={setPersona} />
        <HealthScore score={anomaly_report.overall_health_score ?? null} />
        {metadata.degraded && <DegradedBanner degradedReason={metadata.degraded_reason} />}
        {/* metadata carries a server-side default, so it is not guaranteed
            present on the wire — never dereference it bare. */}
        <SkippedMetricsNotice skippedMetrics={anomaly_report.metadata?.skipped_metrics ?? []} />
        <ParseWarningsNotice warnings={response.warnings} />
        <TelemetryChip response={response} />
      </header>

      {narrative && (
        <section>
          <h2 className="text-sm font-medium tracking-wide text-ink-muted uppercase">Narrative</h2>
          <div className="mt-3">
            <Narrative narrative={narrative} />
          </div>
          {/* The narrative is the one LLM-authored artifact in the report, so
              it is the one most worth asking about. */}
          <div className="mt-3 border-t border-rule pt-2">
            <FeedbackControl jobId={response.job_id} target="narrative" />
          </div>
        </section>
      )}

      {sortedAnomalies.length > 0 && (
        <section>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium tracking-wide text-ink-muted uppercase">
              Anomalies ({sortedAnomalies.length})
            </h2>
          </div>
          <div className="mt-3">
            <ContributionWaterfall anomalies={sortedAnomalies} />
          </div>
          <div className="mt-4 space-y-4">
            {sortedAnomalies.map((anomaly, i) => (
              <div
                key={anomaly.anomaly_id}
                className="motion-safe:animate-[fade-in_300ms_ease-out_backwards]"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <AnomalyCard
                  anomaly={anomaly}
                  highlightedId={highlightedId}
                  onHighlight={setHighlightedId}
                  jobId={response.job_id}
                  source={sourceByMetricId.get(anomaly.metric_id)}
                  persona={persona}
                />
                {prescriptionsByAnomalyId.has(anomaly.anomaly_id) && (
                  <div className="mt-2 rounded-sm border border-rule border-t-0 p-5">
                    <PrescriptionCard prescription={prescriptionsByAnomalyId.get(anomaly.anomaly_id)!} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {matched_cases.length > 0 && (
        <section>
          <h2 className="text-sm font-medium tracking-wide text-ink-muted uppercase">Similar cases</h2>
          <div className="mt-3">
            <MatchedCases cases={matched_cases} />
          </div>
        </section>
      )}

      <Highlights highlights={anomaly_report.non_anomalous_highlights} />

      {/* Last: these are evidence, not the headline. A reader who wants to
          know where the numbers came from and how they were reached finds
          both after reading them. */}
      <SourceManifestPanel manifest={response.source_manifest} />
      <MethodPanel response={response} />
      {persona === "executive" && <EntitlementNote />}
    </div>
  );
}
