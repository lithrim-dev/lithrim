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
    getByText("REJECT");
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
    getByText(/no verdict yet/i); // honest placeholder
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

  it("renders the per-judge votes inline (role + realized vote)", () => {
    const { getByText, getAllByText } = render(
      <VerdictCard verdict="approve" agreement="3 / 3" votes={VOTES} runId="run-10" />,
    );
    getByText("risk_judge");
    getByText("policy_judge");
    getByText("faithfulness_judge");
    expect(getAllByText("PASS").length).toBeGreaterThanOrEqual(2); // the two PASS votes
    getByText("WARN");
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
