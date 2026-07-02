/* ScorecardCard.test.jsx — RUN-ALL-1: the consolidated cohort scorecard renders inline.
   Verifies it reads the BFF `scorecard` payload (flat-spread props): headline precision/recall/
   verdict-accuracy, per-case caught/missed/spurious chips, honest-unlabeled, and that it's wired
   into the renderTool registry under tool-scorecard. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ScorecardCard from "./ScorecardCard.jsx";
import { renderTool, KNOWN_TOOLS } from "./index.js";

const CARD = {
  cases: [
    { case_id: "case01", verdict: "BLOCK", labeled: true, gold: ["INTENT_ERASURE"], caught: ["INTENT_ERASURE"], missed: [], spurious: [] },
    { case_id: "case06", verdict: "BLOCK", labeled: true, gold: ["VALUE_MISMATCH"], caught: [], missed: ["VALUE_MISMATCH"], spurious: ["INTERNAL_INCONSISTENCY"] },
    { case_id: "case08", verdict: "PASS", labeled: true, gold: [], caught: [], missed: [], spurious: [] },
    { case_id: "draftX", verdict: "WARN", labeled: false, raised: ["HALLUCINATED_DETAIL"] },
  ],
  n_cases: 4, n_labeled: 3,
  flag: { tp: 1, fp: 1, fn: 1, precision: 0.5, recall: 0.5 },
  verdict_accuracy: "3/3",
  by_flag: { INTERNAL_INCONSISTENCY: { tp: 0, fp: 1, fn: 0 }, VALUE_MISMATCH: { tp: 0, fp: 0, fn: 1 } },
  grade_path: "live",
};

describe("ScorecardCard (tool-scorecard)", () => {
  it("renders headline metrics + per-case caught/missed/spurious", () => {
    render(<ScorecardCard {...CARD} />);
    expect(screen.getByText(/Scorecard · 4 cases/)).toBeInTheDocument();
    expect(screen.getAllByText("50%").length).toBe(2);           // precision + recall both 0.5
    expect(screen.getByText("3/3")).toBeInTheDocument();         // verdict match
    // per-case rows exist
    expect(screen.getByTestId("scorecard-row-case01")).toBeInTheDocument();
    expect(screen.getByTestId("scorecard-row-case06")).toBeInTheDocument();
    // case06 shows the FP + the miss
    const row = screen.getByTestId("scorecard-row-case06");
    expect(row.textContent).toMatch(/FP/);
    expect(row.textContent).toMatch(/miss/i);
  });

  it("shows clean ✓ on a perfect labeled case and 'unlabeled' on a draft", () => {
    render(<ScorecardCard {...CARD} />);
    expect(screen.getByTestId("scorecard-row-case08").textContent).toMatch(/clean/);
    expect(screen.getByTestId("scorecard-row-draftX").textContent).toMatch(/unlabeled/);
  });

  it("summarizes over-fires and misses from by_flag", () => {
    render(<ScorecardCard {...CARD} />);
    expect(screen.getByTestId("scorecard-overfired").textContent).toMatch(/×1/);
    expect(screen.getByTestId("scorecard-missed").textContent).toMatch(/×1/);
  });

  it("is registered + renders via the renderTool registry (flat-spread output)", () => {
    expect(KNOWN_TOOLS).toContain("tool-scorecard");
    const el = renderTool({ type: "tool-scorecard", state: "output-available", output: CARD });
    expect(el).toBeTruthy();
    render(el);
    expect(screen.getByTestId("scorecard-card")).toBeInTheDocument();
  });

  it("opens a case's full run when its row is clicked (onOpenCaseRun drill-down)", () => {
    const onOpenCaseRun = vi.fn();
    render(<ScorecardCard {...CARD} onOpenCaseRun={onOpenCaseRun} />);
    const row = screen.getByTestId("scorecard-row-case06");
    expect(row).toHaveAttribute("role", "button"); // clickable affordance only when wired
    fireEvent.click(row);
    expect(onOpenCaseRun).toHaveBeenCalledWith("case06");
  });

  it("renders static rows (no button role) when no drill-down handler is wired", () => {
    render(<ScorecardCard {...CARD} />);
    expect(screen.getByTestId("scorecard-row-case06")).not.toHaveAttribute("role", "button");
  });

  it("renders an honest empty state with no cases", () => {
    render(<ScorecardCard cases={[]} />);
    expect(screen.getByText(/run all cases/i)).toBeInTheDocument();
  });
});

describe("ScorecardCard — FLOOR-VIS-1: the units dual-report", () => {
  const UNITS = { tp: 88, fp: 55, fn: 35, matched_gold: 84, precision: 0.615, recall: 0.706 };

  it("renders the units line next to strict when the scorecard carries units", () => {
    render(<ScorecardCard {...CARD} units={UNITS} />);
    const u = screen.getByTestId("scorecard-units");
    expect(u).toHaveTextContent(/units/i);
    expect(u).toHaveTextContent("62%"); // precision 0.615 → rounded pct
    expect(u).toHaveTextContent("71%"); // recall 0.706
  });

  it("renders NO units line when the payload has none (legacy scorecards, honest-absent)", () => {
    render(<ScorecardCard {...CARD} />);
    expect(screen.queryByTestId("scorecard-units")).toBeNull();
  });
});
