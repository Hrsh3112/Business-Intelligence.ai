"use client";

import type { Persona } from "@/lib/api";

interface PersonaSwitcherProps {
  persona: Persona;
  onChange: (persona: Persona) => void;
}

const PERSONAS: { value: Persona; label: string; blurb: string }[] = [
  {
    value: "executive",
    label: "Executive",
    blurb: "Situation, actions and what's at stake. Statistical detail withheld.",
  },
  {
    value: "analyst",
    label: "Analyst",
    blurb: "Everything, plus z-scores, noise confidence and method provenance.",
  },
];

/**
 * Persona view switch (critique P0 #1 / P1 #8).
 *
 * A live toggle rather than a re-upload: the two views are of the SAME
 * computed report, and switching between them in place is what makes that
 * legible. Nothing here changes a number — it changes which numbers a given
 * reader is entitled to see.
 */
export function PersonaSwitcher({ persona, onChange }: PersonaSwitcherProps) {
  const active = PERSONAS.find((p) => p.value === persona) ?? PERSONAS[0];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-rule p-3">
      <div>
        <p className="text-xs font-medium tracking-wide text-ink-muted uppercase">Viewing as</p>
        <p className="mt-0.5 text-sm text-ink-muted">{active.blurb}</p>
      </div>
      <div role="group" aria-label="Select persona" className="flex shrink-0 gap-1">
        {PERSONAS.map((option) => {
          const isActive = option.value === persona;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              aria-pressed={isActive}
              className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
                isActive ? "border-ink bg-ink text-ground" : "border-rule text-ink-muted hover:text-ink"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * The honest caveat, rendered wherever fields are withheld. Presentation-layer
 * redaction is a demonstration of entitlement, not an enforcement of it — the
 * payload still contains every field, and anyone with the API can fetch it.
 * Saying so is the difference between showing a security model and claiming
 * one we did not build.
 */
export function EntitlementNote() {
  return (
    <p className="text-[11px] text-ink-muted">
      Role is enforced server-side by API key. Field-level redaction is applied at the API layer.
      Row-level security would be enforced at the data source in production.
    </p>
  );
}
