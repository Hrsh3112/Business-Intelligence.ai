import type { components } from "@/types/api";
import type { MetricSource, Persona } from "@/lib/api";
import { FeedbackControl } from "./FeedbackControl";
import { SeverityConfidenceBar } from "./SeverityConfidenceBar";
import { Sparkline } from "./Sparkline";

type Anomaly = components["schemas"]["Anomaly"];

interface AnomalyCardProps {
  anomaly: Anomaly;
  highlightedId: string | null;
  onHighlight: (id: string | null) => void;
  jobId: string;
  /** Provenance for this metric, when the submission carried one. Absent for
   *  computed metrics that were never submitted directly. */
  source?: MetricSource;
  persona: Persona;
}

const DIRECTION_LABEL: Record<string, string> = {
  above_expected: "above expected",
  below_expected: "below expected",
};

/**
 * The most important component in the app (Phase3-Plan T3.4). Carries the
 * signature severity/confidence marker plus every null-handling case that
 * WILL occur on real data.
 */
export function AnomalyCard({
  anomaly,
  highlightedId,
  onHighlight,
  jobId,
  source,
  persona,
}: AnomalyCardProps) {
  // Entitlement: the analyst view carries the statistical apparatus, the
  // executive view carries the business fact. Both read the same computed
  // report — nothing here recomputes or rounds differently per persona.
  const showStatistics = persona === "analyst";
  const isSelf = highlightedId === anomaly.anomaly_id;
  const isPartner = highlightedId !== null && anomaly.correlated_anomalies.includes(highlightedId);
  const isHighlighted = isSelf || isPartner;

  // deviation.direction: "as_expected" semantics are still open (Contract
  // O13) — it can only appear on an Anomaly, but an anomaly deviated by
  // definition, so seeing it at all is worth a console note. Render
  // neutrally either way; never crash on the unhandled/unrecognised case.
  let directionLabel = DIRECTION_LABEL[anomaly.deviation.direction];
  if (directionLabel === undefined) {
    console.warn(`AnomalyCard: unhandled deviation.direction "${anomaly.deviation.direction}" (O13 still open)`);
    directionLabel = "relative to expected";
  }

  const delta = anomaly.deviation.observed_current - anomaly.deviation.expected_value;
  const hasTrendData = anomaly.trend.values_over_time !== null && anomaly.trend.values_over_time !== undefined;

  return (
    <article
      id={`anomaly-${anomaly.anomaly_id}`}
      className={`rounded-sm border p-5 transition-colors duration-150 motion-reduce:transition-none ${
        isHighlighted ? "border-accent bg-accent/[0.04]" : "border-rule bg-white/40"
      }`}
      onMouseEnter={() => onHighlight(anomaly.anomaly_id)}
      onMouseLeave={() => onHighlight(null)}
    >
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-xs font-medium tracking-wide text-ink-muted uppercase">{anomaly.category}</p>
            {(anomaly.source_system || source?.source_system) && (
              <span className="rounded-xs border border-rule bg-white/70 px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase text-ink-muted">
                {anomaly.source_system ?? source?.source_system}
                {anomaly.data_as_of && ` · ${anomaly.data_as_of}`}
              </span>
            )}
            {anomaly.driver_rank === 1 && (
              <span
                className="rounded-xs border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase text-accent"
                title={(anomaly as any).granger_tested ? "Identified as primary driver via Granger lead-lag causality" : "Identified as primary driver via magnitude heuristic"}
              >
                Primary Driver{(anomaly as any).granger_tested ? " · Granger" : ""}
              </span>
            )}
          </div>
          <h3 className="font-display text-lg font-medium text-ink">{anomaly.metric_display_name}</h3>
        </div>
        <span className="shrink-0 text-xs font-medium tracking-wide text-ink-muted uppercase">
          {anomaly.severity_label}
        </span>
      </header>

      {anomaly.noise_confidence !== null && anomaly.noise_confidence !== undefined && (
        <div className="mt-4">
          <SeverityConfidenceBar severityScore={anomaly.severity_score} noiseConfidence={anomaly.noise_confidence} />
        </div>
      )}

      {anomaly.contribution_pct !== null && anomaly.contribution_pct !== undefined && (
        <div className="mt-3 rounded-sm border border-rule bg-white/30 p-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-ink-muted">Contribution to health score drop</span>
            <span className="data font-medium text-ink">{anomaly.contribution_pct.toFixed(1)}%</span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-rule">
            <div
              className="h-full bg-accent transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(0, anomaly.contribution_pct))}%` }}
              title={`This metric's weighted severity accounts for ${anomaly.contribution_pct.toFixed(1)}% of the overall health score deterioration.`}
            />
          </div>
        </div>
      )}

      <div className="data mt-4 grid grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-xs text-ink-muted">Observed</p>
          <p className="text-ink">{anomaly.deviation.observed_current.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-xs text-ink-muted flex items-center gap-1">
            Expected
            {(anomaly as any).baseline_source === "ets_personalised" ? (
              <span className="rounded border border-accent/40 bg-accent/10 px-1 text-[9px] font-medium uppercase text-accent" title="Personalised Holt-Winters ETS baseline">ETS</span>
            ) : (
              <span className="text-[9px] text-ink-muted/70 uppercase" title="Static sector-parametric cohort baseline">Sector</span>
            )}
          </p>
          <p className="text-ink">{anomaly.deviation.expected_value.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-xs text-ink-muted">Delta</p>
          <p className="text-ink">
            {delta >= 0 ? "+" : ""}
            {delta.toFixed(2)} <span className="text-ink-muted">({directionLabel})</span>
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-end justify-between gap-4">
        <div>
          {hasTrendData ? (
            <Sparkline points={anomaly.trend.values_over_time!} />
          ) : (
            <p className="text-xs text-ink-muted italic">trend needs 6+ periods</p>
          )}
          {/* slope / acceleration / periods_deviating: omit the row entirely when null, don't render a blank. */}
          {showStatistics && anomaly.trend.slope !== null && anomaly.trend.slope !== undefined && (
            <p className="data mt-1 text-xs text-ink-muted">
              slope {anomaly.trend.slope >= 0 ? "+" : ""}
              {anomaly.trend.slope.toFixed(3)}/period
              {anomaly.trend.periods_deviating !== null && anomaly.trend.periods_deviating !== undefined && (
                <> · {anomaly.trend.periods_deviating} periods deviating</>
              )}
            </p>
          )}
        </div>
        <p className="text-xs text-ink-muted capitalize">{anomaly.trend.direction}</p>
      </div>

      {anomaly.context_tags.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {anomaly.context_tags.map((tag) => (
            <span
              key={tag}
              className="rounded-sm border border-rule px-1.5 py-0.5 text-[11px] text-ink-muted"
            >
              {tag.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}

      {anomaly.correlated_anomalies.length > 0 && (
        <p className="mt-3 text-xs text-ink-muted">
          Correlated with{" "}
          {anomaly.correlated_anomalies.map((id, i) => (
            <span key={id}>
              {i > 0 && ", "}
              <button
                type="button"
                className="cursor-pointer underline decoration-dotted underline-offset-2 hover:text-accent"
                onMouseEnter={() => onHighlight(id)}
                onFocus={() => onHighlight(id)}
                onClick={() => document.getElementById(`anomaly-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
              >
                {id}
              </button>
            </span>
          ))}
        </p>
      )}

      {/* Method provenance per anomaly (critique P0 #3: "no method label on
          any anomaly card"). Every figure above — z-score, severity, the
          noise verdict — came from deterministic code, and the card should
          say so where the numbers are, not only in the panel at the end. */}
      {anomaly.noise_confidence !== null && anomaly.noise_confidence !== undefined && anomaly.noise_confidence < 0.5 && (
        <p className="mt-3 rounded-sm border border-rule bg-white/40 p-2 text-[11px] text-ink-muted">
          Weak signal — {(anomaly.noise_confidence * 100).toFixed(0)}% confidence this is structural
          rather than noise. Treat it as a question, not a finding: more periods would settle whether
          this is a real shift or normal variation.
        </p>
      )}

      {source && (
        <p className="mt-3 text-[11px] text-ink-muted">
          Source: {source.source_system ?? "not declared"}
          {source.source_basis === "upload_filename" && " (from filename)"} · {source.grain} · as of{" "}
          <span className="data">{source.as_of_period}</span> · {source.points} points
          {source.interpolated_points > 0 && `, ${source.interpolated_points} gap-filled`}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-rule pt-2">
        {showStatistics && anomaly.deviation.z_score !== null && anomaly.deviation.z_score !== undefined ? (
          <p className="max-w-prose text-[11px] text-ink-muted">
            Detected deterministically · z {anomaly.deviation.z_score.toFixed(2)} · percentile{" "}
            {anomaly.deviation.percentile.toFixed(1)}
            {anomaly.noise_confidence !== null && anomaly.noise_confidence !== undefined && ` · signal confidence ${(anomaly.noise_confidence * 100).toFixed(0)}%`}
            {` · severity ${anomaly.severity_score.toFixed(1)}/100`} · no LLM involved in any figure on this card
          </p>
        ) : (
          <p className="max-w-prose text-[11px] text-ink-muted">
            Detected deterministically · no LLM involved in any figure on this card
          </p>
        )}
        <FeedbackControl
          jobId={jobId}
          target="anomaly"
          anomalyId={anomaly.anomaly_id}
          metricId={anomaly.metric_id}
        />
      </div>
    </article>
  );
}
