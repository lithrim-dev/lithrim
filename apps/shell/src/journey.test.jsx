/* journey.test.jsx — SHEPHERD-1 (W5): the rail-derivation helper (W1) + the rail render
   (the static "4 / 6" literal is gone) + the save->advance flip (W3). Hermetic, no fetch. */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { deriveSteps, nextStep, isSampleLeaked } from "./journey.js";
import { LeftRail } from "./panes.jsx";

const cfg = (ep) => ({ name: "eval-1", eval_profile: ep });
const stateOf = (d, name) => d.steps.find((s) => s.name === name).state;

describe("SHEPHERD-1 W1 — deriveSteps maps live state to the plan", () => {
  it("an empty agent → Domain current, the rest todo, 0 / 5", () => {
    const d = deriveSteps(cfg({}), [], "eval-1", null);
    expect(stateOf(d, "Domain")).toBe("current");
    expect(stateOf(d, "Judges")).toBe("todo");
    expect(stateOf(d, "Run")).toBe("todo");
    expect(d.done).toBe(0);
    expect(d.total).toBe(5); // KB is optional → excluded from the denominator
  });

  it("a null agentCfg → all todo with Domain current (the offline / pre-fetch fallback)", () => {
    const d = deriveSteps(null, [], "eval-1", null);
    expect(stateOf(d, "Domain")).toBe("current");
    expect(d.done).toBe(0);
  });

  it("an ontology_ref → Domain done, Judges current", () => {
    const d = deriveSteps(cfg({ ontology_ref: "support_ticket_qa/1" }), [], "eval-1", null);
    expect(stateOf(d, "Domain")).toBe("done");
    expect(stateOf(d, "Judges")).toBe("current");
    expect(d.done).toBe(1);
  });

  it("+ judges → Judges done, Ground truth current", () => {
    const d = deriveSteps(
      cfg({ ontology_ref: "x/1", judges: ["risk_judge"] }), [], "eval-1", null,
    );
    expect(stateOf(d, "Judges")).toBe("done");
    expect(stateOf(d, "Ground truth")).toBe("current");
    expect(d.done).toBe(2);
  });

  it("+ tools OR grounding_checks → Ground truth done", () => {
    const viaTools = deriveSteps(
      cfg({ ontology_ref: "x/1", judges: ["r"], tools: ["dosage_grounding"] }), [], "eval-1", null,
    );
    expect(stateOf(viaTools, "Ground truth")).toBe("done");
    const viaChecks = deriveSteps(
      cfg({ ontology_ref: "x/1", judges: ["r"], grounding_checks: ["c1"] }), [], "eval-1", null,
    );
    expect(stateOf(viaChecks, "Ground truth")).toBe("done");
  });

  it("KB is done-but-NEVER-current (optional, never blocks/leads)", () => {
    // KB bound but Ground truth NOT → current stays on Ground truth, KB shows done.
    const d = deriveSteps(
      cfg({ ontology_ref: "x/1", judges: ["r"], kb_bindings: { hipaa: "ns" } }), [], "eval-1", null,
    );
    expect(stateOf(d, "Knowledge base")).toBe("done");
    expect(stateOf(d, "Ground truth")).toBe("current"); // KB skipped when choosing current
    expect(d.steps.every((s) => !(s.name === "Knowledge base" && s.state === "current"))).toBe(true);
    expect(d.total).toBe(5); // KB never counts toward the denominator
  });

  it("a run for THIS agent → Run done; a run for ANOTHER agent does not count", () => {
    const ep = { ontology_ref: "x/1", judges: ["r"], tools: ["t"] };
    const mine = deriveSteps(cfg(ep), [{ agent: "eval-1" }], "eval-1", null);
    expect(stateOf(mine, "Run")).toBe("done");
    const other = deriveSteps(cfg(ep), [{ agent: "other" }], "eval-1", null);
    expect(stateOf(other, "Run")).toBe("current"); // not this agent's run
  });

  it("Review is a distinct beat: current when Run done but no result viewed; done when runResult loaded", () => {
    const ep = { ontology_ref: "x/1", judges: ["r"], tools: ["t"] };
    const runs = [{ agent: "eval-1" }];
    const beforeView = deriveSteps(cfg(ep), runs, "eval-1", null);
    expect(stateOf(beforeView, "Run")).toBe("done");
    expect(stateOf(beforeView, "Review")).toBe("current"); // run exists, not yet reviewed
    const afterView = deriveSteps(cfg(ep), runs, "eval-1", { verdict: "approve" });
    expect(stateOf(afterView, "Review")).toBe("done");
    expect(afterView.done).toBe(5); // the whole required journey complete
  });

  it("nextStep returns the first incomplete required step's name, null when complete", () => {
    expect(nextStep(deriveSteps(cfg({}), [], "eval-1", null))).toBe("Domain");
    const full = deriveSteps(
      cfg({ ontology_ref: "x/1", judges: ["r"], tools: ["t"] }),
      [{ agent: "eval-1" }], "eval-1", { verdict: "approve" },
    );
    expect(nextStep(full)).toBeNull();
  });
});

describe("SHEPHERD-1 W1 — LeftRail renders the derived plan (the '4 / 6' literal is gone)", () => {
  const base = { width: 270, agents: ["eval-1"], activeAgent: "eval-1",
    onNewEval: () => {}, onSwitchAgent: () => {}, onDeleteAgent: () => {} };

  it("renders the derived count, not the static 4 / 6", () => {
    const d = deriveSteps(cfg({ ontology_ref: "x/1" }), [], "eval-1", null);
    render(<LeftRail {...base} steps={d.steps} journeyCount={{ done: d.done, total: d.total }} />);
    expect(screen.queryByText("4 / 6")).toBeNull(); // the literal is gone
    expect(screen.getByText("1 / 5")).toBeInTheDocument(); // Domain done, KB excluded
    expect(screen.getByText("Domain")).toBeInTheDocument();
    expect(screen.getByText("Run")).toBeInTheDocument();
  });

  it("falls back to the static template when no derived steps are passed (offline)", () => {
    render(<LeftRail {...base} />);
    // the template still renders (no blank rail); the count derives from the template states.
    expect(screen.getByText("Domain")).toBeInTheDocument();
    expect(screen.queryByText("4 / 6")).toBeNull();
  });
});

describe("SHEPHERD-1 W3 — save → advance: deriveSteps re-derive flips a step done", () => {
  it("before a judge save Judges is current; after (judges non-empty) it flips done", () => {
    const beforeSave = deriveSteps(cfg({ ontology_ref: "x/1", judges: [] }), [], "eval-1", null);
    expect(stateOf(beforeSave, "Judges")).toBe("current");
    // the save wrote a judge → the next refreshJourney returns judges non-empty
    const afterSave = deriveSteps(cfg({ ontology_ref: "x/1", judges: ["risk_judge"] }), [], "eval-1", null);
    expect(stateOf(afterSave, "Judges")).toBe("done");
    expect(afterSave.done).toBe(beforeSave.done + 1);
  });
});

describe("EVAL-FLOW A2 — Ground truth ticks on a saved grounding contract (the ontology source)", () => {
  // E-D1 option (i): the rail reads the ontology's verification_contracts (the SAME store the
  // grade consumes + loop.py:158 claims), threaded as deriveSteps' 5th param `contracts`. The
  // existing tools/grounding_checks OR-clause is KEPT as a superset; this adds the honest tick.
  const judged = { ontology_ref: "x/1", judges: ["risk_judge"] }; // Domain+Judges done, Ground truth current

  it("Ground truth NOT done when no contract exists (contracts=[]) — NON-VACUOUS", () => {
    const d = deriveSteps(cfg(judged), [], "eval-1", null, []);
    expect(stateOf(d, "Ground truth")).toBe("current");
    expect(d.done).toBe(2); // Domain + Judges only
  });

  it("Ground truth FLIPS done once a verification contract exists (contracts=[{flag_code}])", () => {
    const d = deriveSteps(cfg(judged), [], "eval-1", null, [{ flag_code: "WRONG_DOSAGE" }]);
    expect(stateOf(d, "Ground truth")).toBe("done");
    expect(d.done).toBe(3); // Domain + Judges + Ground truth
  });

  it("the contracts param is the 5th positional arg + defaults to [] (existing call sites stay green)", () => {
    // a 4-arg call (no contracts) keeps the legacy behavior: Ground truth current here.
    const legacy = deriveSteps(cfg(judged), [], "eval-1", null);
    expect(stateOf(legacy, "Ground truth")).toBe("current");
  });

  it("KEEPS the eval_profile.tools/grounding_checks superset clause (back-compat)", () => {
    const viaTools = deriveSteps(cfg({ ...judged, tools: ["dosage_grounding"] }), [], "eval-1", null, []);
    expect(stateOf(viaTools, "Ground truth")).toBe("done"); // still ticks via the old store
  });
});

describe("READINESS — a pack-declared floor the agent can't run un-ticks Ground truth", () => {
  // The silent hole: a verification_contract present (Ground truth would tick) but the pinned pack
  // declares a fact-check this agent can't run → the floor fires silently-never. The rail must NOT
  // read green. The 6th param `readiness` carries the preflight report; an ERROR finding un-ticks.
  const judged = { ontology_ref: "x/1", judges: ["risk_judge"] };
  const contracts = [{ flag_code: "FABRICATED_CLAIM" }]; // Ground truth would otherwise tick

  const degraded = { ok: false, findings: [{ check: "CONTRACT_COVERAGE", severity: "ERROR", code: "snomed_subsumption(FABRICATED_CLAIM)" }] };
  const ready = { ok: true, findings: [] };
  const warnOnly = { ok: true, findings: [{ check: "LENS_VS_CONTRACT_GAP", severity: "WARN", code: "HALLUCINATED_DETAIL" }] };

  it("an ERROR finding un-ticks Ground truth even with a contract present (NON-VACUOUS)", () => {
    const d = deriveSteps(cfg(judged), [], "eval-1", null, contracts, degraded);
    expect(stateOf(d, "Ground truth")).toBe("current");
  });

  it("an ok report leaves Ground truth done (readiness passes)", () => {
    const d = deriveSteps(cfg(judged), [], "eval-1", null, contracts, ready);
    expect(stateOf(d, "Ground truth")).toBe("done");
  });

  it("a WARN-only report does NOT un-tick (only ERRORs block)", () => {
    const d = deriveSteps(cfg(judged), [], "eval-1", null, contracts, warnOnly);
    expect(stateOf(d, "Ground truth")).toBe("done");
  });

  it("readiness defaults to null → prior behavior (existing call sites stay green)", () => {
    const d = deriveSteps(cfg(judged), [], "eval-1", null, contracts);
    expect(stateOf(d, "Ground truth")).toBe("done");
  });
});

describe("EVAL-FLOW A4 — Run ticks on a run for the active agent (with the new 5th param)", () => {
  const ep = { ontology_ref: "x/1", judges: ["r"] };
  const contracts = [{ flag_code: "WRONG_DOSAGE" }]; // Ground truth done via the new source

  it("a run whose agent === activeAgent ticks Run done", () => {
    const d = deriveSteps(cfg(ep), [{ agent: "eval-1" }], "eval-1", null, contracts);
    expect(stateOf(d, "Run")).toBe("done");
  });

  it("a run for ANOTHER agent does NOT tick Run (NON-VACUOUS)", () => {
    const d = deriveSteps(cfg(ep), [{ agent: "other" }], "eval-1", null, contracts);
    expect(stateOf(d, "Run")).toBe("current"); // Ground truth done, Run is now current
  });
});

describe("SHEPHERD-1c — roster-add on judge save flips the Judges step (S-BS-153)", () => {
  // S-BS-153: the JudgeEditor save now passes the active agent, so the server rosters the
  // role onto eval_profile.judges (idempotent, audited). The rail predicate is unchanged
  // (correct, pure) — what flips it is that the per-agent ROSTER (not the separate per-role
  // JudgeConfig store) is now non-empty after the save. This pins the end-to-end semantics
  // the rail relies on: an empty roster (the pre-1c JudgeEditor save) does NOT tick Judges;
  // a roster-add does.
  it("an empty eval_profile.judges leaves Judges NOT done (the pre-1c gap)", () => {
    const d = deriveSteps(cfg({ ontology_ref: "x/1", judges: [] }), [], "eval-1", null);
    expect(stateOf(d, "Judges")).not.toBe("done");
  });

  it("the roster-add (judges := [role]) ticks Judges done — idempotent on repeat", () => {
    const onceRostered = deriveSteps(cfg({ ontology_ref: "x/1", judges: ["risk_judge"] }), [], "eval-1", null);
    expect(stateOf(onceRostered, "Judges")).toBe("done");
    // a second save of the same role is a server-side no-op → the roster is unchanged, still done
    const twiceRostered = deriveSteps(cfg({ ontology_ref: "x/1", judges: ["risk_judge"] }), [], "eval-1", null);
    expect(stateOf(twiceRostered, "Judges")).toBe("done");
    expect(twiceRostered.done).toBe(onceRostered.done);
  });
});

// UI-pass 2026-07-04 P1 #9: the rail numbered steps POSITIONALLY (KB=4, Review=6) while the
// counter said "/ 5" — a guide reader counting along tripped. `num` numbers REQUIRED steps
// only (1..total); the optional KB carries num=null (the rail renders a dot).
describe("deriveSteps — required-step numbering matches the done/total counter", () => {
  it("numbers required steps 1..total and gives the optional KB step num=null", () => {
    const d = deriveSteps(null, [], null, null);
    const byName = Object.fromEntries(d.steps.map((s) => [s.name, s]));
    expect(byName["Knowledge base"].optional).toBe(true);
    expect(byName["Knowledge base"].num).toBeNull();
    const requiredNums = d.steps.filter((s) => !s.optional).map((s) => s.num);
    expect(requiredNums).toEqual([1, 2, 3, 4, 5]); // contiguous — Review is 5 of 5, never "6 / 5"
    expect(d.total).toBe(5);
  });
});

// SHEPHERD-1 F2-refine: the leaked-sample guard blanked `ws0_default`'s journey on ANY
// non-`default` workspace — but once the sample has been genuinely graded on THIS workspace
// (a run exists; runs are the active workspace's, server-scoped by out_dir) it is a real
// evaluation, not a leaked seed, so it must show its true journey.
describe("isSampleLeaked — a graded ws0_default is not a leaked sample", () => {
  const RUN = { agent: "ws0_default", run_id: "r1" };

  it("never leaked on the `default` workspace (the sample's home)", () => {
    expect(isSampleLeaked("default", "ws0_default", [])).toBe(false);
    expect(isSampleLeaked("default", "ws0_default", [RUN])).toBe(false);
  });

  it("a non-default workspace with a fresh (un-run) ws0_default IS leaked (blank journey)", () => {
    expect(isSampleLeaked("clinverdict-guide", "ws0_default", [])).toBe(true);
  });

  it("a non-default workspace whose ws0_default has a run is NOT leaked (used here)", () => {
    expect(isSampleLeaked("clinverdict-guide", "ws0_default", [RUN])).toBe(false);
  });

  it("only ws0_default's OWN runs release the guard (another agent's run does not) — NON-VACUOUS", () => {
    expect(isSampleLeaked("clinverdict-guide", "ws0_default", [{ agent: "eval-1" }])).toBe(true);
  });

  it("a real (non-ws0_default) agent is never treated as the leaked sample", () => {
    expect(isSampleLeaked("clinverdict-guide", "eval-1", [])).toBe(false);
  });

  it("tolerates a null/absent runs list", () => {
    expect(isSampleLeaked("clinverdict-guide", "ws0_default", null)).toBe(true);
    expect(isSampleLeaked("clinverdict-guide", "ws0_default")).toBe(true);
  });
});
