/**
 * The largest element on the page (Phase3-Plan T3.3). The null case is not a
 * footnote: Contract §7.1 is explicit that a refusal must never render
 * "50/100" — this is the highest-traffic path in the refusal demo.
 *
 * P2: a meter accompanies the number. The critique's point was that a grey
 * numeral on white does not read under projector light, and it is right — but
 * the number stays primary and the band is a secondary cue, because the score
 * is a continuous measure and a three-colour traffic light would imply
 * thresholds C1 does not define. The band is derived here purely for legibility
 * and is never presented as a computed classification.
 *
 * On refusal there is no bar at all. A zero-width or grey track next to "N/A"
 * would read as "scored, and bad" — the exact misreading the N/A rule exists
 * to prevent.
 */
interface HealthScoreProps {
  score: number | null;
}

function band(score: number): { label: string; className: string } {
  // Presentation bands only. C1 owns severity thresholds; these describe the
  // health score for a reader and are deliberately not sourced from
  // severity_bands, which measure a different thing in the other direction.
  if (score >= 70) return { label: "healthy", className: "bg-ink" };
  if (score >= 40) return { label: "mixed", className: "bg-ink-muted" };
  return { label: "strained", className: "bg-flag" };
}

export function HealthScore({ score }: HealthScoreProps) {
  if (score === null) {
    return (
      <div>
        <div className="data font-display text-6xl font-medium tracking-tight text-ink-muted sm:text-7xl">
          N/A
        </div>
        <p className="mt-2 text-sm text-ink-muted">not scored — insufficient data</p>
      </div>
    );
  }

  const { label, className } = band(score);
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <div>
      <div className="data font-display text-6xl font-medium tracking-tight text-ink sm:text-7xl">
        {score.toFixed(1)}
        <span className="text-2xl font-normal text-ink-muted sm:text-3xl"> / 100</span>
      </div>

      <div
        className="mt-3 h-2 w-full max-w-sm overflow-hidden rounded-[2px] bg-rule"
        role="img"
        aria-label={`Overall health score ${score.toFixed(1)} of 100 — ${label}`}
      >
        <div
          className={`h-full ${className} transition-[width] duration-500 motion-reduce:transition-none`}
          style={{ width: `${clamped}%` }}
        />
      </div>

      <p className="mt-2 text-sm text-ink-muted">
        overall health score · <span className="text-ink">{label}</span>
      </p>
    </div>
  );
}
