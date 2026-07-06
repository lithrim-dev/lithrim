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

  it("renders the per-sample K-split chip from scores_raw (R2c) — and never fabricates one", () => {
    const votes = [
      { role: "reviewer_gpt41", vote: "PASS", scores_raw: [0.0, 0.0, 1.0, 1.0, 1.0], k: 5 },
      { role: "reviewer_opus", vote: "BLOCK" }, // unsampled: no split chip
    ];
    const { getByTestId, queryByTestId } = render(
      <VerdictCard verdict="approve" votes={votes} runId="run-10" />,
    );
    expect(getByTestId("vote-split-reviewer_gpt41")).toHaveTextContent("2B/3P");
    expect(queryByTestId("vote-split-reviewer_opus")).toBeNull();
  });

  it("R2c dual-confidence: BOTH the logprob and the self-report confidence render side by side", () => {
    const votes = [
      { role: "reviewer_gpt41", vote: "PASS", confidence: 0.71, confidence_self: 0.6, k: 5 },
    ];
    const { getByTestId, container } = render(
      <VerdictCard verdict="approve" votes={votes} runId="run-10" />,
    );
    // the logprob channel keeps rendering as the primary confidence number
    expect(container.textContent).toMatch(/0\.71/);
    // the self-report (sampled decision aggregate) renders alongside it, distinctly
    expect(getByTestId("vote-selfconf-reviewer_gpt41")).toHaveTextContent(/0\.60/);
  });

  it("R2c: a vote with only a logprob confidence shows NO fabricated self-report chip", () => {
    const votes = [{ role: "reviewer_opus", vote: "PASS", confidence: 0.9 }];
    const { queryByTestId } = render(
      <VerdictCard verdict="approve" votes={votes} runId="run-10" />,
    );
    expect(queryByTestId("vote-selfconf-reviewer_opus")).toBeNull();
  });

  it("k=1 hides the meaningless variance chip; a multi-sample vote keeps it (UI-pass polish)", () => {
    const votes = [
      { role: "reviewer_composo", vote: "BLOCK", variance: 0.0, k: 1 }, // "var 0.00 · k=1" was noise
      { role: "reviewer_gpt41", vote: "PASS", variance: 0.13, k: 5 },
    ];
    const { container } = render(<VerdictCard verdict="approve" votes={votes} runId="run-10" />);
    expect(container.textContent).not.toMatch(/var 0\.00 · k=1/);
    expect(container.textContent).toMatch(/var 0\.13 · k=5/);
  });

  it("F8: a single GRADED reward score renders on the row; a decision scalar never does", () => {
    const votes = [
      { role: "reviewer_composo", vote: "BLOCK", scores_raw: [0.26], k: 1 }, // graded reward score
      { role: "reviewer_opus", vote: "PASS", scores_raw: [1], k: 1 }, // plain decision scalar
    ];
    const { getByTestId, queryByTestId } = render(
      <VerdictCard verdict="approve" votes={votes} runId="run-10" />,
    );
    expect(getByTestId("vote-score-reviewer_composo")).toHaveTextContent("score 0.26");
    expect(queryByTestId("vote-score-reviewer_opus")).toBeNull(); // never fabricated
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

  // FLOOR-CLEAR-1: the symmetric case — a judge RAISED a finding that a deterministic floor then
  // DISPROVED (grounded.suppressed). The SNOMED-subsumption flip the demo turns on must read inline:
  // the false alarm + the rule that cleared it + the evidence, so the punchline isn't only in the report.
  it("renders a 'cleared by a fact-check' attribution from floorClears on a pass (the suppression flip)", () => {
    const floorClears = [
      { flag: "FABRICATED_HISTORY", reason: "grounded in the record by SNOMED subsumption",
        evidence: "all 1 documented PMH item(s) are == or subsumed-by a record concept (oracle codes=[31996006])" },
    ];
    const { getByText, container } = render(
      <VerdictCard verdict="approve" agreement="2 / 3" votes={[]} floorClears={floorClears} runId="r" />,
    );
    expect(container.textContent).toMatch(/cleared by a fact-check/i); // the attribution label
    getByText("Fabricated history"); // the suppressed code, rendered readable
    expect(container.textContent).toMatch(/subsumed-by/); // the deterministic evidence
  });

  it("shows NO floor-clear attribution when there are no floorClears (no fabricated 'cleared' on a real pass)", () => {
    const { container } = render(<VerdictCard verdict="approve" agreement="3 / 3" votes={[]} runId="r" />);
    expect(container.textContent).not.toMatch(/cleared by a fact-check/i);
  });

  // REL-OPS-1 O2: a terminology-grounded suppression carries the release that decided it —
  // rendered as muted secondary metadata; a legacy (pre-O2) entry renders exactly as before.
  it("renders the terminology edition on a floorClears entry that carries it", () => {
    const floorClears = [
      { flag: "FABRICATED_CLAIM", reason: "code-grounded by is-a subsumption via the connected terminology tool",
        evidence: "every flagged term is ==/subsumed-by a record concept", terminology_edition: "unrecorded" },
    ];
    const { container } = render(
      <VerdictCard verdict="approve" agreement="2 / 3" votes={[]} floorClears={floorClears} runId="r" />,
    );
    expect(container.textContent).toMatch(/terminology edition: unrecorded/);
  });

  it("renders NO edition text on a legacy floorClears entry without the field (no placeholder)", () => {
    const floorClears = [
      { flag: "FABRICATED_HISTORY", reason: "grounded in the record by SNOMED subsumption",
        evidence: "all 1 documented PMH item(s) are == or subsumed-by a record concept" },
    ];
    const { container } = render(
      <VerdictCard verdict="approve" agreement="2 / 3" votes={[]} floorClears={floorClears} runId="r" />,
    );
    expect(container.textContent).not.toMatch(/terminology edition/i);
    expect(container.textContent).not.toMatch(/undefined/);
  });
});
