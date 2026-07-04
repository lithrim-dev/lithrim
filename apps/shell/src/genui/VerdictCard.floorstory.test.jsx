/* VerdictCard.floorstory.test.jsx — FLOOR-STORY-1 on the INLINE chat card (the shared
   binding: adapter.py/panes.jsx feed council.case_outcome as caseOutcome). On a
   floor-cleared run (verdict pass + floorClears) the headline must never contradict
   the pass with a harsh outcome, and the same flip-story copy as the Report banner
   renders. A genuinely-flagged card (no clears) is unchanged. */
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import VerdictCard from "./VerdictCard.jsx";

vi.mock("../bff.js", () => ({ recordMetaVerdict: vi.fn().mockResolvedValue({ status: "ok" }) }));

const CLEARS = [
  { flag: "FABRICATED_CLAIM", reason: "is-a subsumption" },
  { flag: "FABRICATED_CLAIM", reason: "is-a subsumption" },
  { flag: "FABRICATED_HISTORY", reason: "present in the record" },
];

describe("VerdictCard — FLOOR-STORY-1: floor-cleared coherence", () => {
  it("a pre-fix contradicting caseOutcome (FLAGGED) over an APPROVE with clears reads Passed, not Flagged", () => {
    const { container } = render(
      <VerdictCard verdict="APPROVE" caseOutcome="FLAGGED" floorClears={CLEARS}
        answer="No findings — passes the quality gate." />,
    );
    const badge = container.querySelector(".icard-hd .tag");
    expect(badge.textContent).toBe("Passed");
    expect(badge.className).toMatch(/\bpass\b/);
    expect(badge.className).not.toMatch(/\bfail\b/);
  });

  it("renders the same flip-story copy as the Report banner", () => {
    const { container } = render(
      <VerdictCard verdict="APPROVE" caseOutcome="CLEAR" floorClears={CLEARS} answer="ok" />,
    );
    expect(container.textContent).toMatch(/Reviewers flagged it · a fact-check cleared 3 false alarms · final: Passed/);
  });

  it("a genuinely-flagged card (no clears) still reads Flagged with no story line (pinned)", () => {
    const { container } = render(
      <VerdictCard verdict="REJECT" caseOutcome="FLAGGED" answer="1 finding(s): INTENT_ERASURE" />,
    );
    const badge = container.querySelector(".icard-hd .tag");
    expect(badge.textContent).toBe("Flagged");
    expect(badge.className).toMatch(/\bfail\b/);
    expect(container.textContent).not.toMatch(/fact-check cleared/);
  });

  it("clears on a still-flagged card (partial clear, verdict REJECT) show no false 'final: Passed' story", () => {
    const { container } = render(
      <VerdictCard verdict="REJECT" caseOutcome="FLAGGED" floorClears={[CLEARS[0]]} answer="1 finding(s): X" />,
    );
    expect(container.textContent).not.toMatch(/final: Passed/);
    // the per-row "Cleared by a fact-check" attribution itself stays (pinned)
    expect(container.textContent).toMatch(/Cleared by a fact-check/);
  });
});
