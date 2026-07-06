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
// activeAgent, runResult, contracts).
function isDone(name, ep, runs, activeAgent, runResult, contracts, readiness) {
  switch (name) {
    case "Domain":
      return !!ep.ontology_ref;
    case "Judges":
      return (ep.judges || []).length > 0;
    case "Ground truth":
      // EVAL-FLOW (E-D1 option i): the rail reads the SAME store the grade consumes — the
      // ontology's verification_contracts (App fetches them; loop.py:158 claims this completes
      // Ground truth). The eval_profile.tools/grounding_checks clause is KEPT as a superset.
      // READINESS: presence alone isn't enough — if the pinned pack declares a fact-check this
      // agent can't run (any ERROR finding), the floor would fire SILENTLY-never, so Ground truth
      // is NOT done (it becomes the shepherd's `current` lead). readiness null → prior behavior.
      if (readiness && Array.isArray(readiness.findings) &&
          readiness.findings.some((f) => String(f.severity || "").toUpperCase() === "ERROR")) {
        return false;
      }
      return (
        (contracts || []).length > 0 ||
        (ep.tools || []).length > 0 ||
        (ep.grounding_checks || []).length > 0
      );
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

/* deriveSteps(agentCfg, runs, activeAgent, runResult, contracts) → { steps, done, total }.
   `steps` mirrors STEPS (name/desc) with a derived `state`; `done`/`total` count the
   REQUIRED steps only (KB excluded from the denominator so the optional step never
   inflates "N / 6"). A missing/null agentCfg → all-`todo` with Domain `current`.
   `contracts` (the ontology's verification_contracts, App-fetched) defaults to [] so the
   existing 4-arg call sites stay green; a non-empty list ticks Ground truth (EVAL-FLOW).
   `readiness` (the agent↔pack preflight report) defaults to null (prior behavior); an ERROR
   finding un-ticks Ground truth so a pack floor the agent can't run doesn't read as done. */
export function deriveSteps(agentCfg, runs = [], activeAgent = null, runResult = null, contracts = [], readiness = null) {
  const ep = (agentCfg && agentCfg.eval_profile) || {};
  const doneFlags = STEPS.map((s) => isDone(s.name, ep, runs, activeAgent, runResult, contracts, readiness));

  // `current` = the first incomplete REQUIRED step (skip the optional KB).
  let currentIdx = -1;
  for (let i = 0; i < STEPS.length; i += 1) {
    if (OPTIONAL.has(STEPS[i].name)) continue;
    if (!doneFlags[i]) { currentIdx = i; break; }
  }

  // `num` numbers the REQUIRED steps only (1..total) so the rail's node numbers agree with
  // the "done / total" counter — the optional KB step carries num=null (rendered as a dot),
  // instead of positional numbering that showed "step 6" in a "/ 5" journey.
  let reqNum = 0;
  const steps = STEPS.map((s, i) => ({
    ...s,
    state: doneFlags[i] ? "done" : i === currentIdx ? "current" : "todo",
    optional: OPTIONAL.has(s.name),
    num: OPTIONAL.has(s.name) ? null : (reqNum += 1),
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

/* isSampleLeaked(activeWs, activeAgent, runs) → boolean. SHEPHERD-1 F2 (+ refine).

   `ws0_default` is the shared blank-slate SAMPLE agent, pre-baked with an ontology + judges.
   A freshly-created non-`default` workspace re-seeds it on the first GET /v1/agents read, so
   its pre-baked profile would show stale Domain✓/Judges✓ progress the user never set — the
   guard derives that agent's journey against blank state until a real evaluation is configured.

   REFINE: the sample is only "leaked" while it is UNTOUCHED here. `runs` is the active
   workspace's run list (server-scoped to the workspace out_dir — apps/bff/app.py: "switching
   the workspace switches agents/judges/flags/audit"), so a run whose agent is `ws0_default`
   means the sample has been genuinely graded ON THIS workspace and is a real evaluation, not a
   leaked seed — its true journey should show. On `default` (the sample's home) it is never
   leaked; a non-`ws0_default` agent is never the sample. */
export function isSampleLeaked(activeWs, activeAgent, runs = []) {
  if (activeWs === "default" || activeAgent !== "ws0_default") return false;
  return !(runs || []).some((r) => r && r.agent === "ws0_default");
}
