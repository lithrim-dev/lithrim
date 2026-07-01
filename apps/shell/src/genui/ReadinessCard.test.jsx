/* ReadinessCard.test.jsx — the inline "setup gaps" card (tool-readiness_card).
   The conversational-first surface for the agent↔pack readiness preflight: when a pack-declared
   fact-check can't run for this agent, the human sees WHY inline (not in the closed pane) with a
   one-click remediation. Verifies flat-spread props, the ERROR/WARN rendering, the honest ready
   state, the onFix/onSwitchAgent affordances, and the renderTool registry wiring. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ReadinessCard from "./ReadinessCard.jsx";
import { renderTool, KNOWN_TOOLS } from "./index.js";

const DEGRADED = {
  ok: false,
  pack: "clinverdict",
  agent: "ws0_default",
  ontology_source: "committed",
  assessed: true,
  findings: [
    {
      check: "CONTRACT_COVERAGE", severity: "ERROR",
      code: "snomed_subsumption(FABRICATED_CLAIM)",
      message: "The clinverdict pack declares a snomed_subsumption fact-check for FABRICATED_CLAIM, but agent ws0_default's checklist has no matching fact-check — the floor will silently never fire.",
      remediation: "Add the snomed_subsumption fact-check for FABRICATED_CLAIM to this agent, or switch to a clinverdict-aligned agent.",
    },
    {
      check: "LENS_VS_CONTRACT_GAP", severity: "WARN", code: "HALLUCINATED_DETAIL",
      message: "The council can raise HALLUCINATED_DETAIL but this agent has no grounding floor for it — a confident false positive can't be caught.",
      remediation: "Add a grounding fact-check for HALLUCINATED_DETAIL.",
    },
  ],
};

const READY = { ok: true, pack: "clinverdict", agent: "cv_agent", ontology_source: "draft", assessed: true, findings: [] };

describe("ReadinessCard (tool-readiness_card)", () => {
  it("renders the degraded gaps: message + remediation + severity per finding", () => {
    render(<ReadinessCard {...DEGRADED} />);
    expect(screen.getByTestId("readiness-card")).toBeInTheDocument();
    const row = screen.getByTestId("readiness-finding-CONTRACT_COVERAGE");
    expect(row.textContent).toMatch(/silently never fire/);
    expect(row.textContent).toMatch(/Add the snomed_subsumption fact-check/);
    // both severities present
    expect(screen.getByTestId("readiness-card").textContent).toMatch(/must fix/i);
    expect(screen.getByTestId("readiness-card").textContent).toMatch(/warning/i);
  });

  it("renders an honest ready state when ok", () => {
    render(<ReadinessCard {...READY} />);
    expect(screen.getByTestId("readiness-card").textContent).toMatch(/ready/i);
    // no ERROR findings → no "must fix"
    expect(screen.getByTestId("readiness-card").textContent).not.toMatch(/must fix/i);
  });

  it("fires onFix with the finding when the fix affordance is clicked", () => {
    const onFix = vi.fn();
    render(<ReadinessCard {...DEGRADED} onFix={onFix} />);
    fireEvent.click(screen.getByTestId("readiness-fix-CONTRACT_COVERAGE"));
    expect(onFix).toHaveBeenCalledTimes(1);
    expect(onFix.mock.calls[0][0].check).toBe("CONTRACT_COVERAGE");
  });

  it("offers Switch agent when wired", () => {
    const onSwitchAgent = vi.fn();
    render(<ReadinessCard {...DEGRADED} onSwitchAgent={onSwitchAgent} />);
    fireEvent.click(screen.getByTestId("readiness-switch-agent"));
    expect(onSwitchAgent).toHaveBeenCalled();
  });

  it("is registered + renders via the renderTool registry (flat-spread output)", () => {
    expect(KNOWN_TOOLS).toContain("tool-readiness_card");
    const el = renderTool({ type: "tool-readiness_card", state: "output-available", output: DEGRADED });
    expect(el).toBeTruthy();
    render(el);
    expect(screen.getByTestId("readiness-card")).toBeInTheDocument();
  });
});
