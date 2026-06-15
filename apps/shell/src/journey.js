/* journey.js — SHEPHERD-1 (W1): the setup-journey rail's plan derivation.

   The rail IS the shepherd's plan surface. `deriveSteps` is a PURE function (no fetch,
   no React) that maps the live config + run state to the 6-step plan with a per-step
   `state ∈ {done, current, todo}` + a {done,total} count over the REQUIRED steps. App
   fetches GET /v1/agent + GET /v1/runs and feeds them here; panes.jsx renders the result.

   Mapping (driver §2 W1 + the monitor's Review decision):
     - Domain        done ⟺ eval_profile.ontology_ref truthy
     - Judges        done ⟺ eval_profile.judges non-empty
     - Ground truth  done ⟺ eval_profile.tools non-empty OR grounding_checks present
     - Knowledge base OPTIONAL — done ⟺ kb_bindings non-empty; never `current`/blocking
     - Run           done ⟺ ≥1 run for the active agent (client-filtered)
     - Review        done ⟺ a run result is loaded/viewed (runResult non-null); else
                     `current` once Run is done — a distinct guided beat, not a Run dupe

   `current` = the FIRST incomplete REQUIRED step (KB is optional, so it is skipped when
   choosing `current`). The static STEPS template (data.jsx) supplies name/desc; this
   layers the derived state on top. */

import { STEPS } from "./data.jsx";

// KB is the one optional step — it never blocks progress and is never the `current` lead.
const OPTIONAL = new Set(["Knowledge base"]);

function nonEmptyObj(v) {
  return v && typeof v === "object" && Object.keys(v).length > 0;
}

// Per-step done predicates, keyed by the template `name`. Pure over (agentCfg, runs,
// activeAgent, runResult).
function isDone(name, ep, runs, activeAgent, runResult) {
  switch (name) {
    case "Domain":
      return !!ep.ontology_ref;
    case "Judges":
      return (ep.judges || []).length > 0;
    case "Ground truth":
      return (ep.tools || []).length > 0 || (ep.grounding_checks || []).length > 0;
    case "Knowledge base":
      return nonEmptyObj(ep.kb_bindings);
    case "Run":
      return (runs || []).some((r) => r && r.agent === activeAgent);
    case "Review":
      return runResult != null;
    default:
      return false;
  }
}

/* deriveSteps(agentCfg, runs, activeAgent, runResult) → { steps, done, total }.
   `steps` mirrors STEPS (name/desc) with a derived `state`; `done`/`total` count the
   REQUIRED steps only (KB excluded from the denominator so the optional step never
   inflates "N / 6"). A missing/null agentCfg → all-`todo` with Domain `current`. */
export function deriveSteps(agentCfg, runs = [], activeAgent = null, runResult = null) {
  const ep = (agentCfg && agentCfg.eval_profile) || {};
  const doneFlags = STEPS.map((s) => isDone(s.name, ep, runs, activeAgent, runResult));

  // `current` = the first incomplete REQUIRED step (skip the optional KB).
  let currentIdx = -1;
  for (let i = 0; i < STEPS.length; i += 1) {
    if (OPTIONAL.has(STEPS[i].name)) continue;
    if (!doneFlags[i]) { currentIdx = i; break; }
  }

  const steps = STEPS.map((s, i) => ({
    ...s,
    state: doneFlags[i] ? "done" : i === currentIdx ? "current" : "todo",
  }));

  // The count is over the required steps only (KB is optional).
  const required = STEPS.filter((s) => !OPTIONAL.has(s.name));
  const total = required.length;
  const done = STEPS.filter((s, i) => !OPTIONAL.has(s.name) && doneFlags[i]).length;

  return { steps, done, total };
}

/* The next incomplete REQUIRED step's name (the shepherd-aware empty state's secondary
   chip + the "next step" affordance). Null when the required journey is complete. */
export function nextStep(derived) {
  const cur = (derived.steps || []).find((s) => s.state === "current");
  return cur ? cur.name : null;
}
