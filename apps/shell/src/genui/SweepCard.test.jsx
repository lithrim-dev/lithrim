/* SweepCard.test.jsx — RIGOR-1 / Q1 (NEW-G3): the single-reviewer K-sweep self-consistency card.
   Renders the GET /v1/reliability/{agent}/sweep `sweep` payload (flat-spread) as a per-K series:
   flip-rate / majority-convergence / variance, each with its Wilson CI. The load-bearing honesty
   test: an insufficient/thin sweep renders an honest empty state, NEVER a fabricated number. Wired
   into the renderTool registry under tool-sweep_card. */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SweepCard from "./SweepCard.jsx";
import { renderTool, KNOWN_TOOLS } from "./index.js";

const prop = (value, extra = {}) => ({ value, n: 8, insufficient: false, ci: [0.1, 0.9], ...extra });

// a REAL sweep curve (the endpoint's `sweep` payload, flat-spread)
const REAL = {
  insufficient: false,
  k_max: 5,
  series: [
    { k: 1, flip_rate: prop(0.5), majority_convergence: prop(0.5), variance: prop(0.22) },
    { k: 3, flip_rate: prop(0.2), majority_convergence: prop(0.8), variance: prop(0.12) },
    { k: 5, flip_rate: prop(0.0, { ci: [0.0, 0.3] }), majority_convergence: prop(1.0), variance: prop(0.05) },
  ],
};

const THIN = { insufficient: true, k_max: 0, series: [], reason: "no sampled runs yet" };

describe("SweepCard (tool-sweep_card)", () => {
  it("renders the per-K series with flip-rate / majority-convergence / variance", () => {
    render(<SweepCard {...REAL} />);
    const card = screen.getByTestId("sweep-card");
    expect(card).toBeInTheDocument();
    // one row per K in the series
    expect(screen.getAllByTestId("sweep-row").length).toBe(3);
    // the flip-rate at K=1 (50%) and at K=5 (0%) both render
    expect(card.textContent).toMatch(/50%|0\.5/);
    expect(card.textContent).toMatch(/K\s*=?\s*5|k5/i);
  });

  it("renders an HONEST empty state when the sweep is insufficient — no fabricated number", () => {
    render(<SweepCard {...THIN} />);
    const card = screen.getByTestId("sweep-card");
    expect(card.textContent).toMatch(/No sampled runs yet|not enough data/i);
    expect(card.textContent).not.toMatch(/NaN/);
    expect(screen.queryAllByTestId("sweep-row").length).toBe(0);
  });

  it("renders an honest empty state when nothing is passed at all", () => {
    render(<SweepCard />);
    expect(screen.getByTestId("sweep-card")).toBeInTheDocument();
    expect(screen.getByText(/No sampled runs yet|not enough data/i)).toBeInTheDocument();
  });

  it("is wired into the renderTool registry (flat-spread output)", () => {
    expect(KNOWN_TOOLS).toContain("tool-sweep_card");
    const el = renderTool({ type: "tool-sweep_card", state: "output-available", output: REAL });
    render(el);
    expect(screen.getByTestId("sweep-card")).toBeInTheDocument();
  });
});
