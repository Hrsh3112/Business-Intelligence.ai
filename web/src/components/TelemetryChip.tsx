import type { ApiResponse } from "@/lib/api";

interface TelemetryChipProps {
  response: ApiResponse;
}

function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function formatUsd(usd: number): string {
  // A single analysis costs a fraction of a cent, so fixed 2dp would render
  // every real figure as "$0.00" — which reads as free rather than cheap.
  // Widen the decimals as the number shrinks, and no further: more places
  // than the value needs would imply measured precision we do not have.
  if (usd < 0.001) return `$${usd.toFixed(6)}`;
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

/**
 * Runtime telemetry, surfaced (critique P0 #4). Every figure here was already
 * being computed and sent — latency in ApiResponse.timings, tokens and model
 * in the enrichment metadata — and rendered nowhere.
 *
 * The cost is labelled "est." on purpose. It is derived from a published rate
 * in llm_pricing.yaml, not measured spend, and the basis is available on hover
 * so the number can be defended rather than just displayed. When the backend
 * cannot stand behind a figure it sends null, and we say "no LLM call" instead
 * of printing $0.00 — the refusal path spending nothing is a feature worth
 * stating, not an absence to hide.
 */
export function TelemetryChip({ response }: TelemetryChipProps) {
  const { timings, cost } = response;
  if (!timings) return null;

  const parts: string[] = [formatMs(timings.total_ms)];
  if (timings.c1_ms != null) parts.push(`detection ${formatMs(timings.c1_ms)}`);
  if (timings.c3_ms != null) parts.push(`enrichment ${formatMs(timings.c3_ms)}`);

  if (cost?.tokens_used != null) {
    parts.push(`${cost.tokens_used.toLocaleString()} tokens`);
  }

  if (cost?.estimated_usd != null) {
    parts.push(`~${formatUsd(cost.estimated_usd)} est.`);
  } else if (timings.c3_ms == null) {
    // Refusal path: C3 was never called. Say so — it is the cheapest possible
    // demonstration that abstaining costs nothing.
    parts.push("no LLM call");
  }

  return (
    <p
      className="data text-right text-xs text-ink-muted"
      title={cost?.basis ?? undefined}
      data-testid="telemetry-chip"
    >
      {parts.join(" · ")}
    </p>
  );
}
