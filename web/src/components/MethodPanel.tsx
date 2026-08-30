"use client";

import { useState } from "react";
import type { ApiResponse } from "@/lib/api";
import { DETERMINISTIC_STAGE_COUNT, METHOD_KIND_LABEL, METHODS } from "@/lib/methods";

interface MethodPanelProps {
  response: ApiResponse;
}

// The LLM row must stand out from the deterministic ones, but NOT by using
// --accent: globals.css reserves that colour for the confidence/severity
// signature element, and spending it here would dilute the one hue that
// carries meaning. Weight and contrast do the job instead.
const KIND_STYLE: Record<string, string> = {
  llm: "border-ink font-medium text-ink",
  ml: "border-accent/40 bg-accent/5 font-medium text-accent",
  default: "border-rule text-ink-muted",
};

/**
 * "How we did this" (critique P0 #3) — the explicit LLM vs non-LLM breakdown
 * the problem statement asks for, shown to the user rather than buried in a
 * document nobody opens.
 *
 * Collapsed by default: it is evidence, not the headline. The summary line is
 * the claim that matters and is readable without expanding.
 *
 * The LLM row is rendered from live response data — real model name, real
 * token count, and "not called" when the run was refused or degraded. A static
 * row would keep claiming an LLM ran on the one screen that proves it didn't.
 */
export function MethodPanel({ response }: MethodPanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  const llmRow = METHODS.find((m) => m.kind === "llm")!;
  const deterministicRows = METHODS.filter((m) => m.kind !== "llm");

  const cost = response.cost;
  const narrativePresent = Boolean(response.result?.narrative);
  const llmModel = cost?.llm_model ?? response.result?.metadata?.llm_model ?? null;

  let llmStatus: string;
  if (response.status === "refused") {
    llmStatus = "not called — evidence was insufficient, so no narrative was generated";
  } else if (!narrativePresent) {
    llmStatus = "not called — narrative unavailable, deterministic results shown";
  } else if (llmModel && cost?.tokens_used != null) {
    llmStatus = `${llmModel} · ${cost.tokens_used.toLocaleString()} tokens`;
  } else if (llmModel) {
    llmStatus = llmModel;
  } else {
    llmStatus = "not called";
  }

  return (
    <section className="rounded-sm border border-rule">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 p-3 text-left"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span className="text-sm text-ink">
          How we did this —{" "}
          <span className="text-ink-muted">
            {DETERMINISTIC_STAGE_COUNT} analytical stages (ML, statistical & deterministic), exactly 1 LLM call
          </span>
        </span>
        <span aria-hidden className="shrink-0 text-xs text-ink-muted">
          {isOpen ? "hide" : "show"}
        </span>
      </button>

      {isOpen && (
        <div className="border-t border-rule p-3">
          <p className="max-w-prose text-sm leading-relaxed text-ink-muted">
            Every number shown in this report is computed, not generated. The model is given
            pre-computed values and asked only to write prose — it never measures, scores, or
            decides anything.
          </p>

          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-rule">
                  <th className="py-1.5 pr-3 text-xs font-medium tracking-wide text-ink-muted uppercase">
                    Stage
                  </th>
                  <th className="py-1.5 pr-3 text-xs font-medium tracking-wide text-ink-muted uppercase">
                    Method
                  </th>
                  <th className="py-1.5 text-xs font-medium tracking-wide text-ink-muted uppercase">
                    Technique
                  </th>
                </tr>
              </thead>
              <tbody>
                {deterministicRows.map((method) => (
                  <tr key={method.stage} className="border-b border-rule/60 align-top">
                    <td className="py-1.5 pr-3 whitespace-nowrap text-ink">{method.stage}</td>
                    <td className="py-1.5 pr-3">
                      <span
                        className={`inline-block rounded-sm border px-1.5 py-0.5 text-[11px] font-medium tracking-wide uppercase ${KIND_STYLE[method.kind] ?? KIND_STYLE.default}`}
                      >
                        {METHOD_KIND_LABEL[method.kind]}
                      </span>
                    </td>
                    <td className="py-1.5 text-ink-muted">{method.technique}</td>
                  </tr>
                ))}

                <tr className="align-top">
                  <td className="py-1.5 pr-3 whitespace-nowrap text-ink">{llmRow.stage}</td>
                  <td className="py-1.5 pr-3">
                    <span
                      className={`inline-block rounded-sm border px-1.5 py-0.5 text-[11px] font-medium tracking-wide uppercase ${KIND_STYLE.llm}`}
                    >
                      {METHOD_KIND_LABEL.llm}
                    </span>
                  </td>
                  <td className="py-1.5 text-ink-muted">
                    {llmRow.technique}
                    <span className="mt-0.5 block text-xs">This run: {llmStatus}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
