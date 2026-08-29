"use client";

import { useState } from "react";
import { submitFeedback, type FeedbackCorrection, type FeedbackRequest } from "@/lib/api";

interface FeedbackControlProps {
  jobId: string;
  target?: FeedbackRequest["target"];
  anomalyId?: string;
  /** Corrections offered after a thumbs-down. Anomaly cards get the noise and
   *  severity options; the narrative gets the root-cause one. */
  corrections?: { value: FeedbackCorrection; label: string }[];
}

type State = "idle" | "sending" | "done" | "failed";

const ANOMALY_CORRECTIONS: { value: FeedbackCorrection; label: string }[] = [
  { value: "was_noise", label: "This was noise" },
  { value: "severity_understated", label: "More severe than scored" },
  { value: "severity_overstated", label: "Less severe than scored" },
];

const NARRATIVE_CORRECTIONS: { value: FeedbackCorrection; label: string }[] = [
  { value: "wrong_root_cause", label: "Wrong root cause" },
  { value: "severity_overstated", label: "Overstated" },
];

export { ANOMALY_CORRECTIONS, NARRATIVE_CORRECTIONS };

/**
 * Thumbs up/down plus a structured correction (critique P1 #5 / Req 7, which
 * previously scored zero — there was no feedback mechanism anywhere).
 *
 * Deliberately quiet: this sits at the edge of a report someone is reading, so
 * no modal, no toast, no blocking spinner. A failed submission says so in
 * place and does nothing else — losing a feedback line must never disturb the
 * results on screen.
 *
 * The copy says "recorded", never "we'll learn from this". The backend appends
 * to a file and nothing reads it back yet; promising a learning loop we
 * haven't built is the one thing that would turn an honest answer to Req 7
 * into a claim we can't defend.
 */
export function FeedbackControl({ jobId, target = "report", anomalyId, corrections }: FeedbackControlProps) {
  const [state, setState] = useState<State>("idle");
  const [showCorrections, setShowCorrections] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const options = corrections ?? (target === "anomaly" ? ANOMALY_CORRECTIONS : NARRATIVE_CORRECTIONS);

  async function send(verdict: FeedbackRequest["verdict"], correction?: FeedbackCorrection) {
    setState("sending");
    try {
      const response = await submitFeedback({
        job_id: jobId,
        target,
        anomaly_id: anomalyId ?? null,
        verdict,
        correction: correction ?? null,
      });
      setState(response.recorded ? "done" : "failed");
      setMessage(response.message);
    } catch {
      // Network failure. Same treatment as a declined write: say so here, and
      // leave everything else on the page alone.
      setState("failed");
      setMessage("Couldn't send that — your report is unaffected.");
    }
    setShowCorrections(false);
  }

  if (state === "done" || state === "failed") {
    return <p className="text-[11px] text-ink-muted">{message}</p>;
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-muted">
      <span>Useful?</span>
      <button
        type="button"
        disabled={state === "sending"}
        onClick={() => send("useful")}
        className="rounded-sm border border-rule px-1.5 py-0.5 hover:text-ink disabled:opacity-50"
        aria-label="Mark this as useful"
      >
        Yes
      </button>
      <button
        type="button"
        disabled={state === "sending"}
        onClick={() => setShowCorrections(!showCorrections)}
        className="rounded-sm border border-rule px-1.5 py-0.5 hover:text-ink disabled:opacity-50"
        aria-expanded={showCorrections}
        aria-label="Mark this as not useful"
      >
        No
      </button>

      {showCorrections && (
        <>
          <span aria-hidden>·</span>
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={state === "sending"}
              onClick={() => send("not_useful", option.value)}
              className="rounded-sm border border-rule px-1.5 py-0.5 hover:text-ink disabled:opacity-50"
            >
              {option.label}
            </button>
          ))}
          <button
            type="button"
            disabled={state === "sending"}
            onClick={() => send("not_useful")}
            className="underline decoration-dotted underline-offset-2 hover:text-ink disabled:opacity-50"
          >
            just not useful
          </button>
        </>
      )}
    </div>
  );
}
