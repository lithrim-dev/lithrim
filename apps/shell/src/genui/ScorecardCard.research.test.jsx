/* ScorecardCard.research.test.jsx — REPRO-1 R3: the research read surface renders inline —
   the per-reviewer table (matches/misses/over-flags per model) + the cross-model majority row,
   the case × reviewer matrix (vote + raw K-split per cell, gold column), and the floor tallies
   (cleared / enforced / cannot-ground, gold-defect clears MUST-be-zero highlighted, verdict
   accuracy pre → post floor). All keys are additive on the same flat-spread scorecard payload;
   a cohort with no votes/floor data renders exactly the old card (back-compat is the existing
   ScorecardCard.test.jsx). */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ScorecardCard from "./ScorecardCard.jsx";

const BASE = {
  cases: [
    { case_id: "c1", verdict: "reject", labeled: true, gold: ["FABRICATED_CLAIM"], caught: ["FABRICATED_CLAIM"], missed: [], spurious: [] },
  ],
  n_cases: 1, n_labeled: 1,
  flag: { tp: 1, fp: 0, fn: 0, precision: 1.0, recall: 1.0 },
  verdict_accuracy: "1/1",
  by_flag: {},
};

const RESEARCH = {
  ...BASE,
  by_judge: [
    { judge_role: "reviewer_a", model: "gpt-4.1", n: 10, matches_gold: 6, misses: 4, over_flags: 0 },
    { judge_role: "reviewer_b", model: "claude-opus-4-8", n: 10, matches_gold: 4, misses: 6, over_flags: 0 },
  ],
  majority: { n: 10, matches_gold: 6, misses: 3, over_flags: 0, ties: 1 },
  judge_matrix: [
    {
      case_id: "c1", gold: "BLOCK", verdict: "reject", majority: "TIE",
      cells: [
        { judge_role: "reviewer_a", model: "gpt-4.1", vote: "BLOCK", scores_raw: [0, 0, 0, 0, 0] },
        { judge_role: "reviewer_b", model: "claude-opus-4-8", vote: "PASS", scores_raw: [1, 1, 1, 1, 1] },
      ],
    },
  ],
  floor: {
    cleared: 9, enforced: 4, inconclusive: 1,
    gold_defect_clears: [],
    verdict_accuracy_pre_floor: 0.5, verdict_accuracy_post_floor: 0.9,
  },
};

describe("ScorecardCard — the research read surface (R3)", () => {
  it("renders the per-reviewer table with the majority row", () => {
    render(<ScorecardCard {...RESEARCH} />);
    const table = screen.getByTestId("scorecard-by-judge");
    expect(table.textContent).toMatch(/gpt-4\.1/);
    expect(table.textContent).toMatch(/claude-opus-4-8/);
    const a = screen.getByTestId("by-judge-row-reviewer_a");
    expect(a.textContent).toMatch(/6/);
    expect(a.textContent).toMatch(/4/);
    const maj = screen.getByTestId("by-judge-majority");
    expect(maj.textContent).toMatch(/majority/i);
    expect(maj.textContent).toMatch(/1/); // the tie count is visible, never hidden
  });

  it("renders the case × reviewer matrix with vote + K-split cells and the gold column", () => {
    render(<ScorecardCard {...RESEARCH} />);
    const row = screen.getByTestId("judge-matrix-row-c1");
    expect(row.textContent).toMatch(/5B/);   // reviewer_a's split
    expect(row.textContent).toMatch(/5P/);   // reviewer_b's split
    expect(row.textContent).toMatch(/BLOCK/i); // the gold column
  });

  it("renders the floor tallies with the pre→post accuracy and the safety property", () => {
    render(<ScorecardCard {...RESEARCH} />);
    const floor = screen.getByTestId("scorecard-floor");
    expect(floor.textContent).toMatch(/9/);   // cleared
    expect(floor.textContent).toMatch(/4/);   // enforced
    expect(floor.textContent).toMatch(/50%/); // pre-floor accuracy
    expect(floor.textContent).toMatch(/90%/); // post-floor accuracy
    expect(floor.textContent).toMatch(/0 genuine defects cleared/i); // the safety property
  });

  it("names a gold-defect clear loudly when the safety property is violated", () => {
    const bad = {
      ...RESEARCH,
      floor: { ...RESEARCH.floor, gold_defect_clears: [{ case_id: "c9", code: "FABRICATED_CLAIM" }] },
    };
    render(<ScorecardCard {...bad} />);
    const alarm = screen.getByTestId("scorecard-gold-defect-clears");
    expect(alarm.textContent).toMatch(/c9/);
    expect(alarm.textContent).toMatch(/fabricated claim/i); // flagLabel humanizes the code
  });

  it("renders none of the research sections when the keys are absent (back-compat)", () => {
    render(<ScorecardCard {...BASE} />);
    expect(screen.queryByTestId("scorecard-by-judge")).toBeNull();
    expect(screen.queryByTestId("scorecard-floor")).toBeNull();
  });
});
