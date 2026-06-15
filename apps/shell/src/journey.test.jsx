/* journey.test.jsx — SHEPHERD-1 (W5): the rail-derivation helper (W1) + the rail render
   (the static "4 / 6" literal is gone) + the save->advance flip (W3). Hermetic, no fetch. */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { deriveSteps, nextStep } from "./journey.js";
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
