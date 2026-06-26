/* VerdictCard.test.jsx — the verdict card must (a) render REAL output (no hardcoded
   DEMO masquerading as a verdict) and (b) drive its color/icon from the verdict, so a
   REJECT reads negative (coral/fail), not a green "pass" pill + coral check.
   [[no-static-components-in-live-eval-ui]] */
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import VerdictCard from "./VerdictCard.jsx";

// the inline dissent form posts via bff.recordMetaVerdict — stub it so mounting the
// card (which embeds ClinicianVerdict) never reaches a real fetch.
vi.mock("../bff.js", () => ({ recordMetaVerdict: vi.fn().mockResolvedValue({ status: "ok" }) }));

describe("VerdictCard — verdict-driven, real-data only", () => {
  it("a REJECT renders the fail (coral) badge, NOT the pass (green) one", () => {
    const { container, getByText } = render(
      <VerdictCard verdict="REJECT" confidence="0.9" agreement="1 / 3" question="Q?" answer="A." pillar="Faithfulness" pillarStatus="flagged" />,
    );
    getByText("Flagged"); // REJECT renders as the plain outcome "Flagged"
    const badge = container.querySelector(".tag");
    expect(badge.className).toMatch(/\bfail\b/); // coral/fail tone
    expect(badge.className).not.toMatch(/\bpass\b/); // never the green pass pill
  });

  it("an APPROVE/PASS renders the pass (green) badge", () => {
    const { container } = render(<VerdictCard verdict="approve" confidence="1.0" agreement="3 / 3" question="Q?" answer="A." />);
    const badge = container.querySelector(".tag");
    expect(badge.className).toMatch(/\bpass\b/);
    expect(badge.className).not.toMatch(/\bfail\b/);
  });

  it("output-less mount renders an honest empty state — NOT a fabricated DEMO verdict", () => {
    const { container, queryByText, getByText } = render(<VerdictCard />);
    getByText(/no result yet/i); // honest placeholder
    expect(queryByText("Sample verdict")).toBeNull(); // no fake title
    expect(container.textContent).not.toMatch(/0\.96|3 \/ 3|refund policy/); // no DEMO leak
    expect(container.querySelector(".tag")).toBeNull(); // no fake verdict badge
  });

  it("judge-agreement dots reflect the real count (1 / 3 -> 1 filled, 2 empty)", () => {
    const { container } = render(<VerdictCard verdict="reject" agreement="1 / 3" question="Q?" answer="A." />);
    const dots = container.querySelectorAll(".agree-dots .ad");
    expect(dots.length).toBe(3);
    expect(container.querySelectorAll(".agree-dots .ad.no").length).toBe(2); // 2 of 3 not-agreeing
  });
});

// CONV-FIRST (SPEC_CONVERSATIONAL_FIRST §3): the inline verdict card is the WHOLE eval
// result — the human completes load → grade → dissent → record without the pane. So the
// card composes per-judge votes + the clinician-verdict (dissent) form inline, with an
// "Open full report →" that opens the pane only on an explicit drill-down.
describe("VerdictCard — fully-interactive inline result", () => {
  const VOTES = [
    { role: "risk_judge", vote: "PASS", confidence: 1.0 },
    { role: "policy_judge", vote: "WARN", confidence: 0.99 },
    { role: "faithfulness_judge", vote: "PASS", confidence: 0.98 },
  ];

  it("renders the per-reviewer votes inline (reviewer name + plain outcome)", () => {
    const { getByText, getAllByText } = render(
      <VerdictCard verdict="approve" agreement="3 / 3" votes={VOTES} runId="run-10" />,
    );
    getByText("Risk reviewer");
    getByText("Policy reviewer");
    getByText("Faithfulness reviewer");
    expect(getAllByText("Passed").length).toBeGreaterThanOrEqual(2); // the two PASS votes
    getByText("Needs a look"); // the WARN vote
  });

  it("renders the clinician-verdict (dissent) form inline when a runId is present", () => {
    const { getByTestId, getByText } = render(
      <VerdictCard verdict="approve" votes={VOTES} runId="run-10" />,
    );
    expect(getByTestId("clinician-verdict")).toBeInTheDocument(); // the dissent form, in the chat
    getByText("Record verdict");
  });

  it("'Open full report →' opens the pane on demand (the explicit drill-down)", () => {
    const onOpenArtifact = vi.fn();
    const { getByText } = render(
      <VerdictCard verdict="approve" votes={VOTES} runId="run-10" onOpenArtifact={onOpenArtifact} />,
    );
    fireEvent.click(getByText(/open full report/i));
    expect(onOpenArtifact).toHaveBeenCalledWith("report");
  });

  it("the empty-state has NO votes and NO inline dissent form", () => {
    const { container, queryByTestId } = render(<VerdictCard />);
    expect(queryByTestId("clinician-verdict")).toBeNull();
    expect(container.querySelector(".ivotes")).toBeNull();
  });
});

// INLINE-IMPACT-1: the card must carry its own WHY — the approve reads as a REASONED verdict
// (each judge's reason inline), and the BLOCK shows WHO caught it (a deterministic floor rule the
// human authored), so the demo's thesis is on screen, not only in the voiceover.
describe("VerdictCard — carries the WHY inline (reasoning + floor attribution)", () => {
  it("renders each judge's reason under their vote (approve reads as reasoned, not a scorecard)", () => {
    const votes = [
      { role: "policy_judge", vote: "PASS", confidence: 0.92, reason: "Documentation aligns with the visit; no safety gap." },
      { role: "risk_judge", vote: "PASS", confidence: 0.9 },
    ];
    const { getByText } = render(<VerdictCard verdict="approve" agreement="2 / 2" votes={votes} runId="r" />);
    getByText(/Documentation aligns with the visit/); // the reason is visible inline
  });

  it("renders a 'Caught by floor rule' attribution from floorBlocks on a BLOCK", () => {
    const floorBlocks = [
      { flag: "DISSENT_ERASURE", contract_type: "value_presence", contract: "DISSENT_ERASURE/v1",
        disposition: "the patient's refusal was stated but missing from the note" },
    ];
    const { getByText, container } = render(
      <VerdictCard verdict="BLOCK" agreement="1 / 3" votes={[]} floorBlocks={floorBlocks} runId="r" />,
    );
    expect(container.textContent).toMatch(/caught by a fact-check/i); // the attribution label
    getByText("Dissent erasure"); // the injected code, rendered readable
    expect(container.textContent).toMatch(/value_presence/); // the deterministic contract that fired
    getByText(/refusal was stated but missing from the note/); // the one-line why
  });

  it("shows NO floor-rule attribution when there are no floorBlocks (no fabricated 'caught' on a clean pass)", () => {
    const { container } = render(<VerdictCard verdict="approve" agreement="3 / 3" votes={[]} runId="r" />);
    expect(container.textContent).not.toMatch(/caught by .*floor/i);
  });
});
