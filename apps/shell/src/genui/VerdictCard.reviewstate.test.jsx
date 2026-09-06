/* VerdictCard.reviewstate.test.jsx — REVIEW-STATE-UI-1 on the inline card (the primary
   surface, SPEC_CONVERSATIONAL_FIRST): when the run carries the engine's review decision,
   the headline is the reviewer state (Flagged / Cleared / Needs a person) with its reason,
   never a harsher outcome label over an unproven signal. No review block → today's headline.
   Written FIRST (RED). */
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import VerdictCard from "./VerdictCard.jsx";

vi.mock("../bff.js", () => ({ recordMetaVerdict: vi.fn().mockResolvedValue({ status: "ok" }) }));

const VOTES = [
  { role: "risk_judge", vote: "BLOCK", confidence: 0.9 },
  { role: "policy_judge", vote: "WARN", confidence: null },
  { role: "faithfulness_judge", vote: "BLOCK", confidence: null },
];

const FLAGGED = {
  state: "FLAGGED", check: "value_grounding",
  evidence: "value_grounding: values stated in the artifact are absent from the record; missing ['50']",
  reason: "a deterministic check contradicted the artifact", floor_backstopped: true,
};
const ESCALATED = {
  state: "ESCALATED", check: null, evidence: "value_grounding confirmed 4 value(s) present",
  reason: "judges raised ['UNSUPPORTED_ASSERTION']; no check could confirm or refute it", floor_backstopped: false,
};
const CLEARED = {
  state: "CLEARED", check: "value_grounding",
  evidence: "value_grounding: 2 value(s) checked, all present in the source",
  reason: "a deterministic check confirmed the artifact", floor_backstopped: true,
};

describe("VerdictCard — the reviewer state is the headline when the run carries one", () => {
  it("ESCALATED: headline Needs a person with the reason, not Critical", () => {
    const { container, getByTestId } = render(
      <VerdictCard verdict="reject" caseOutcome="CRITICAL" votes={VOTES} review={ESCALATED} runId="r1" />,
    );
    expect(container.querySelector(".tag").textContent).toBe("Needs a person");
    expect(container.textContent).not.toMatch(/Critical/);
    expect(getByTestId("review-reason").textContent).toMatch(/no check could confirm or refute it/);
    expect(getByTestId("review-reason").textContent).toMatch(/confirmed 4 value\(s\) present/);
  });

  it("FLAGGED: headline Flagged, coral tone, the check named", () => {
    const { container, getByTestId } = render(
      <VerdictCard verdict="reject" caseOutcome="CRITICAL" votes={VOTES} review={FLAGGED} runId="r2" />,
    );
    expect(container.querySelector(".tag").textContent).toBe("Flagged");
    expect(container.querySelector(".tag").className).toMatch(/\bfail\b/);
    expect(getByTestId("review-reason").textContent).toMatch(/value_grounding/);
  });

  it("CLEARED: headline Cleared, pass tone", () => {
    const { container } = render(
      <VerdictCard verdict="approve" caseOutcome="CLEAR" votes={[]} review={CLEARED} runId="r3" />,
    );
    expect(container.querySelector(".tag").textContent).toBe("Cleared");
    expect(container.querySelector(".tag").className).toMatch(/\bpass\b/);
  });

  it("no review block → today's headline (the outcome label), no reason line", () => {
    const { container, queryByTestId } = render(
      <VerdictCard verdict="reject" caseOutcome="CRITICAL" votes={VOTES} runId="r4" />,
    );
    expect(container.querySelector(".tag").textContent).toBe("Critical");
    expect(queryByTestId("review-reason")).toBeNull();
  });
});
