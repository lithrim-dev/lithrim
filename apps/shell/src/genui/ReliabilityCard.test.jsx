/* ReliabilityCard.test.jsx — feat-reliability-card: the statistical-rigour metrics render
   inline as labeled tiles WITH a plain-English glossary (Term/Tip), and — the load-bearing
   honesty test — an insufficient metric renders an honest "not enough data yet" state, NEVER a
   fabricated number. Real values render when passed. Wired into the renderTool registry under
   tool-reliability_card. */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ReliabilityCard from "./ReliabilityCard.jsx";
import { renderTool, KNOWN_TOOLS } from "./index.js";

const suff = (value, extra = {}) => ({ value, n: 8, insufficient: false, ci: null, ...extra });
const insuff = (reason) => ({ value: null, n: 0, insufficient: true, reason, ci: null });

// a REAL, fully-computed metric set (the endpoint's `metrics` payload, flat-spread)
const REAL = {
  n_runs: 10,
  inter_judge_kappa: suff(0.566),
  cohen_kappa_vs_gold: suff(0.412),
  ece: suff(0.318),
  brier: suff(0.334),
  error_phi: suff(0.21, { n: 6 }),
  effective_votes: suff(2.7, { n: 4 }),
  intra_judge_stability: suff(0.8, { n: 4 }),
  selective_prediction: {
    insufficient: false, n: 8,
    coverage: suff(0.75),
    conditional_accuracy: suff(1.0),
    selective_risk: suff(0.0),
  },
};

// a THIN workspace: everything insufficient (the empty/insufficient state)
const THIN = {
  n_runs: 0,
  inter_judge_kappa: insuff("need at least 2 graded cases with per-judge votes"),
  cohen_kappa_vs_gold: insuff("no labeled cases with judge votes to compare against gold"),
  ece: insuff("no verdicts with both a stated confidence and a gold label"),
  brier: insuff("no verdicts with both a stated confidence and a gold label"),
  error_phi: insuff("need at least 2 judges to correlate errors"),
  effective_votes: insuff("cannot reduce to effective votes without a defined error correlation"),
  intra_judge_stability: insuff("no repeated runs of the same case — needs repeats (K >= 2)"),
  selective_prediction: { insufficient: true, n: 0, reason: "no cases for the floor to cover" },
};

describe("ReliabilityCard (tool-reliability_card)", () => {
  it("renders real metric values as labeled tiles", () => {
    render(<ReliabilityCard {...REAL} />);
    // the coefficient values are shown
    expect(screen.getByTestId("reliability-card")).toBeInTheDocument();
    expect(screen.getByText(/0\.566/)).toBeInTheDocument();  // inter-judge kappa
    expect(screen.getByText(/0\.412/)).toBeInTheDocument();  // cohen kappa
    expect(screen.getByText(/0\.318/)).toBeInTheDocument();  // ECE
    expect(screen.getByText(/0\.334/)).toBeInTheDocument();  // Brier
  });

  it("shows a plain-English glossary (Term/Tip) for each metric", () => {
    render(<ReliabilityCard {...REAL} />);
    // the jargon terms are present as hover-terms (the glossary)
    expect(screen.getByText(/inter-judge agreement/i)).toBeInTheDocument();
    expect(screen.getByText(/vs gold/i)).toBeInTheDocument();
    expect(screen.getAllByText(/calibration error/i).length).toBeGreaterThan(0);
    // each Term carries a title/tooltip attribute with a definition (role=tooltip present)
    expect(screen.getAllByRole("tooltip").length).toBeGreaterThan(0);
  });

  it("renders an HONEST insufficient state — never a fabricated number", () => {
    render(<ReliabilityCard {...THIN} />);
    // no fabricated 0 or 0.0 shows as a metric value; the insufficient copy shows instead
    const card = screen.getByTestId("reliability-card");
    expect(card.textContent).not.toMatch(/\b0\.0\b/);
    // an explicit "not enough data" state appears (at least once, honestly)
    expect(screen.getAllByText(/not enough data/i).length).toBeGreaterThan(0);
    // the reason surfaces (needs repeats / gold)
    expect(card.textContent).toMatch(/repeat|gold|judges|cases/i);
  });

  it("renders an honest empty state when no metrics are passed at all", () => {
    render(<ReliabilityCard />);
    expect(screen.getByTestId("reliability-card")).toBeInTheDocument();
    expect(screen.getByText(/no runs|not enough data|no graded runs/i)).toBeInTheDocument();
  });

  it("is wired into the renderTool registry (flat-spread output)", () => {
    expect(KNOWN_TOOLS).toContain("tool-reliability_card");
    const el = renderTool({ type: "tool-reliability_card", state: "output-available", output: REAL });
    render(el);
    expect(screen.getByTestId("reliability-card")).toBeInTheDocument();
    expect(screen.getByText(/0\.566/)).toBeInTheDocument();
  });

  it("shows selective-prediction coverage/risk when computed, honestly absent otherwise", () => {
    const { rerender } = render(<ReliabilityCard {...REAL} />);
    expect(screen.getAllByText(/coverage/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/75%/)).toBeInTheDocument();  // the real coverage value
    // thin: the floor block reports insufficient, not a fake 0% coverage
    rerender(<ReliabilityCard {...THIN} />);
    const card = screen.getByTestId("reliability-card");
    expect(card.textContent).not.toMatch(/0% coverage/i);
  });
});
