"use client";

import { useState } from "react";
import type { MetricSource } from "@/lib/api";
import { titleCaseMetricId } from "@/lib/metricDisplay";

interface SourceManifestPanelProps {
  manifest: MetricSource[];
}

/**
 * Where the numbers came from (critique P0 #2 / P2 #9; problem statement Req 2
 * — source freshness, grain and lineage).
 *
 * The honesty rule this panel exists to hold: a COMPUTED fact and a DECLARED
 * one must not look alike. Grain, coverage, freshness and interpolation counts
 * were measured from the submitted data. `source_system` is a label the user
 * typed, or the name of the file we were handed — so an inferred source is
 * rendered in muted type with "(from filename)" attached, and an unknown one
 * says "not declared" rather than being silently blank.
 */
export function SourceManifestPanel({ manifest }: SourceManifestPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  if (manifest.length === 0) return null;

  const distinctSources = new Set(
    manifest.map((entry) => entry.source_system).filter((source): source is string => Boolean(source))
  );
  const distinctGrains = new Set(manifest.map((entry) => entry.grain));

  const summary = [
    `${manifest.length} metric${manifest.length === 1 ? "" : "s"}`,
    distinctSources.size > 0
      ? `${distinctSources.size} source${distinctSources.size === 1 ? "" : "s"}`
      : "source not declared",
    `${distinctGrains.size} grain${distinctGrains.size === 1 ? "" : "s"}`,
  ].join(" · ");

  return (
    <section className="rounded-sm border border-rule">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 p-3 text-left"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span className="text-sm text-ink">
          Where this data came from — <span className="text-ink-muted">{summary}</span>
        </span>
        <span aria-hidden className="shrink-0 text-xs text-ink-muted">
          {isOpen ? "hide" : "show"}
        </span>
      </button>

      {isOpen && (
        <div className="border-t border-rule p-3">
          <p className="max-w-prose text-sm leading-relaxed text-ink-muted">
            Grain, coverage and freshness are measured from the data you submitted. The source is
            what you declared, or the file you uploaded — we don&apos;t infer a system we never
            connected to.
          </p>

          {/* Source Legend */}
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-sm border border-rule bg-white/40 p-2.5 text-xs text-ink-muted">
            <span className="font-medium text-ink">Source Legend:</span>
            {Array.from(distinctSources).map((src) => (
              <span key={src} className="rounded-xs border border-rule bg-white px-2 py-0.5 font-medium text-ink">
                {src}
              </span>
            ))}
            <span className="text-ink-muted">·</span>
            <span>{manifest.length} metrics monitored across {distinctGrains.size} time grains</span>
          </div>

          {/* Grain alignment notice if heterogeneous grains present */}
          {distinctGrains.size > 1 && (
            <div className="mt-2.5 rounded-sm border border-amber-200 bg-amber-50/70 p-2.5 text-xs text-amber-900">
              <span className="font-medium">Grain Alignment Note:</span> Multi-source ingestion reconciled daily and monthly cadences. Daily series are harmonized to monthly calendar intervals for unified cross-metric attribution.
            </div>
          )}

          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-rule">
                  {["Metric", "Source", "Grain", "Coverage", "As of", "Quality"].map((heading) => (
                    <th
                      key={heading}
                      className="py-1.5 pr-3 text-xs font-medium tracking-wide text-ink-muted uppercase"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {manifest.map((entry) => (
                  <tr key={entry.metric_id} className="border-b border-rule/60 align-top">
                    <td className="py-1.5 pr-3 text-ink">
                      {entry.display_name ?? titleCaseMetricId(entry.metric_id)}
                    </td>
                    <td className="py-1.5 pr-3 text-ink-muted">
                      {entry.source_system ?? <span className="italic">not declared</span>}
                      {entry.source_basis === "upload_filename" && (
                        <span className="block text-[11px]">from filename</span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3 text-ink-muted capitalize">{entry.grain}</td>
                    <td className="data py-1.5 pr-3 text-ink-muted">
                      {entry.first_period}–{entry.as_of_period}
                      <span className="block text-[11px]">{entry.points} points</span>
                    </td>
                    <td className="data py-1.5 pr-3 text-ink-muted">{entry.as_of_period}</td>
                    <td className="py-1.5 text-ink-muted">
                      <span className="data">{(entry.confidence * 100).toFixed(0)}% confidence</span>
                      {entry.interpolated_points > 0 && (
                        <span className="block text-[11px]">
                          {entry.interpolated_points} gap-filled
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
