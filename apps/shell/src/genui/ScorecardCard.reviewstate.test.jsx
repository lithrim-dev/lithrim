/* ScorecardCard.reviewstate.test.jsx — REVIEW-STATE-UI-2: the batch scorecard speaks the same
   three states as the report pane. Seen live (v0.1.23, ragtruth-queue): "Run eval" on five
   cases rendered "5 flagged" because the card tallied engine verdicts (five BLOCKs), while the
   report pane titled four of them "Needs a person". When every row carries the engine's review
   state, the tally and each row's result word follow it; rows without one keep today's
   verdict wording. Written FIRST (RED). */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ScorecardCard from "./ScorecardCard.jsx";
import { scorecardRead } from "./reportRead.js";

const rv = (state, reason) => ({ state, reason, floor_backstopped: state !== "ESCALATED" });

// the live ragtruth-queue shape: five BLOCK verdicts, one proven by a check, four unproven.
const REVIEW_CARD = {
  cases: [
    { case_id: "ragtruth_10545", verdict: "BLOCK", labeled: true, gold: ["SOURCE_CONTRADICTION"], caught: ["SOURCE_CONTRADICTION"], missed: [], spurious: [], review: rv("FLAGGED", "a deterministic check contradicted the artifact") },
    { case_id: "ragtruth_9001", verdict: "BLOCK", labeled: true, gold: [], caught: [], missed: [], spurious: ["UNSUPPORTED_ASSERTION"], review: rv("ESCALATED", "judges raised ['UNSUPPORTED_ASSERTION']; no check could confirm or refute it") },
    { case_id: "ragtruth_2246", verdict: "BLOCK", labeled: true, gold: ["UNSUPPORTED_ASSERTION"], caught: [], missed: ["UNSUPPORTED_ASSERTION"], spurious: ["MISSING_CONTEXT"], review: rv("ESCALATED", "judges raised ['MISSING_CONTEXT']; no check could confirm or refute it") },
    { case_id: "ragtruth_356", verdict: "BLOCK", labeled: true, gold: ["SOURCE_CONTRADICTION"], caught: ["SOURCE_CONTRADICTION"], missed: [], spurious: [], review: rv("ESCALATED", "judges raised ['SOURCE_CONTRADICTION']; no check could confirm or refute it") },
    { case_id: "ragtruth_12132", verdict: "BLOCK", labeled: true, gold: [], caught: [], missed: [], spurious: ["MISSING_CONTEXT"], review: rv("ESCALATED", "judges raised ['MISSING_CONTEXT']; no check could confirm or refute it") },
  ],
  n_cases: 5, n_labeled: 5,
  flag: { tp: 2, fp: 3, fn: 1, precision: 0.4, recall: 0.667 },
  verdict_accuracy: "3/5",
  by_flag: {},
  grade_path: "in_process",
  // the read band renders only when the floor did something (as the live batch payload had)
  floor: { enforced: 1, cleared: 0, verdict_accuracy_pre_floor: 0.6, verdict_accuracy_post_floor: 0.6 },
};

const CLEARED_ROW = { case_id: "clean_ok", verdict: "PASS", labeled: true, gold: [], caught: [], missed: [], spurious: [], review: rv("CLEARED", "a deterministic check confirmed the artifact") };

// a pre-cycle payload: no review on any row → today's verdict wording, untouched.
const LEGACY_CARD = {
  cases: [
    { case_id: "c1", verdict: "BLOCK", labeled: true, gold: ["X"], caught: ["X"], missed: [], spurious: [] },
    { case_id: "c2", verdict: "WARN", labeled: false, raised: [] },
    { case_id: "c3", verdict: "PASS", labeled: true, gold: [], caught: [], missed: [], spurious: [] },
  ],
  n_cases: 3, n_labeled: 2, flag: { tp: 1, fp: 0, fn: 0, precision: 1, recall: 1 }, verdict_accuracy: "2/2", by_flag: {}, grade_path: "replay",
  floor: { enforced: 1, cleared: 0, verdict_accuracy_pre_floor: 1, verdict_accuracy_post_floor: 1 },
};

describe("ScorecardCard — the tally and the row words follow the review state", () => {
  it("five BLOCKs with one proven defect read '1 flagged · 4 need a person · 0 cleared', never '5 flagged'", () => {
    const { container } = render(<ScorecardCard {...REVIEW_CARD} />);
    expect(screen.getByTestId("scorecard-tally").textContent).toMatch(/1 flagged · 4 need a person · 0 cleared/);
    expect(container.textContent).not.toMatch(/5 flagged/);
  });

  it("each row prints its state: Flagged for the proven one, Needs a person for the rest", () => {
    render(<ScorecardCard {...REVIEW_CARD} />);
    expect(screen.getByTestId("scorecard-row-ragtruth_10545").textContent).toMatch(/Flagged/);
    expect(screen.getByTestId("scorecard-row-ragtruth_10545").textContent).not.toMatch(/Needs a person/);
    for (const id of ["ragtruth_9001", "ragtruth_2246", "ragtruth_356", "ragtruth_12132"]) {
      const row = screen.getByTestId(`scorecard-row-${id}`);
      expect(row.textContent).toMatch(/Needs a person/);
      expect(row.textContent).not.toMatch(/Flagged/);
    }
  });

  it("a CLEARED row prints Cleared and counts in the cleared bucket", () => {
    const card = { ...REVIEW_CARD, cases: [...REVIEW_CARD.cases, CLEARED_ROW], n_cases: 6, n_labeled: 6 };
    render(<ScorecardCard {...card} />);
    expect(screen.getByTestId("scorecard-row-clean_ok").textContent).toMatch(/Cleared/);
    expect(screen.getByTestId("scorecard-tally").textContent).toMatch(/1 flagged · 4 need a person · 1 cleared/);
  });

  it("the row's hover title is the review reason, so the state is explained where it is read", () => {
    render(<ScorecardCard {...REVIEW_CARD} />);
    const row = screen.getByTestId("scorecard-row-ragtruth_9001");
    const word = [...row.querySelectorAll("[title]")].find((el) => /Needs a person/.test(el.textContent));
    expect(word).toBeTruthy();
    expect(word.getAttribute("title")).toMatch(/no check could confirm or refute it/);
  });

  it("rows without a review state render today's verdict wording (pinned)", () => {
    render(<ScorecardCard {...LEGACY_CARD} />);
    expect(screen.getByTestId("scorecard-tally").textContent).toMatch(/1 flagged · 1 need a look · 1 passed/);
    expect(screen.getByTestId("scorecard-row-c1").textContent).toMatch(/Flagged/);
    expect(screen.getByTestId("scorecard-row-c2").textContent).toMatch(/Needs a look/);
    expect(screen.getByTestId("scorecard-row-c3").textContent).toMatch(/Passed/);
  });
});

describe("scorecardRead — the narrative counts by review state when the rows carry it", () => {
  it("says how many a check cleared, flagged, and how many need a person", () => {
    const { text } = scorecardRead(REVIEW_CARD);
    expect(text).toMatch(/0 of 5 .*cleared by a check, 1 flagged, 4 need a person/);
    expect(text).not.toMatch(/passed clean/);
  });

  it("legacy rows keep today's sentence (pinned)", () => {
    const { text } = scorecardRead(LEGACY_CARD);
    expect(text).toMatch(/1 of 3 notes passed clean, 1 was flagged, 1 needs a human look/);
  });
});
