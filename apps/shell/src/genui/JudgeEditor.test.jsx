/* JudgeEditor.test.jsx — UAP-2 R2: the judge-authoring surface loads a judge via
   GET /v1/judges/{role}, refreshes the $0 prompt preview as the assignment changes,
   and PUTs the assignment through bff.js (the SME handle on X-Actor). Mocks bff.js
   (no live BFF) — guards the React side the Python round-trip doesn't. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const SUMMARY = {
  role: "risk_judge",
  model: "",
  assigned_flags: [],
  validator_refs: [],
  available_flags: [
    { flag: "WRONG_DOSAGE", tier: "TIER_1", when_to_use: "dose contradicts the agreed dose", gradeable: true, assigned: false },
    { flag: "FABRICATED_ALLERGY", tier: "TIER_1", when_to_use: "allergy not established", gradeable: true, assigned: false },
  ],
  available_validators: ["dosage_grounding", "structural_jute"],
  questions: [{ ordinal: 1, text: "Did the agent recognize red-flag symptoms?" }],
  authored: false,
  base_prompt: "SEED PROMPT BASE",
  rendered_prompt: "SEED PROMPT BASE",
};

vi.mock("../bff.js", () => ({
  getJudge: vi.fn().mockImplementation((role, opts = {}) => {
    const assigned = opts.assignedFlags || [];
    return Promise.resolve({
      ...SUMMARY,
      role,
      assigned_flags: SUMMARY.assigned_flags,
      // the preview render diverges from base once flags are assigned (the $0 link)
      rendered_prompt: assigned.length
        ? `SEED PROMPT BASE\n=== AUTHORED REFINEMENT (ontology assignment) ===\n- ${assigned.join("\n- ")}`
        : "SEED PROMPT BASE",
    });
  }),
  putJudge: vi.fn().mockResolvedValue({ status: "ok", role: "risk_judge", actor: { type: "user", id: "sme@acme" } }),
  optimizeJudge: vi.fn(),
}));

import JudgeEditor from "./JudgeEditor.jsx";
import { getJudge, putJudge, optimizeJudge } from "../bff.js";

const deltaResult = (delta, { baseline, optimized } = {}) => ({
  role: "risk_judge",
  n_train: 24,
  n_heldout: 10,
  compile_config: { n_demos_bootstrapped: 4, n_positive_demos: delta.graded > 0 ? 2 : 0, coverage_aware: true },
  baseline: baseline || { graded: 0.8, precision: 0.71, recall: 0.71 },
  optimized: optimized || { graded: 0.8 + delta.graded, precision: 0.71 + (delta.precision || 0), recall: 0.71 + (delta.recall || 0) },
  delta,
});

beforeEach(() => {
  getJudge.mockClear();
  putJudge.mockClear();
  optimizeJudge.mockReset();
});

describe("JudgeEditor (tool-judge_editor)", () => {
  it("loads the judge, refreshes the $0 preview on assignment, and PUTs the lens", async () => {
    const onResult = vi.fn();
    render(<JudgeEditor role="risk_judge" onResult={onResult} />);

    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    // the derived refinement question renders ($0, no model)
    expect(screen.getByText(/red-flag symptoms/i)).toBeInTheDocument();
    // the initial load fetches the judge with no assignment (then a preview effect runs)
    expect(getJudge.mock.calls[0]).toEqual(["risk_judge", { agent: "ws0_default" }]);

    // assign a flag → a live preview refetch with assignedFlags (the exact bridge render)
    fireEvent.click(screen.getByLabelText(/assign WRONG_DOSAGE/i));
    await waitFor(() =>
      expect(getJudge).toHaveBeenCalledWith("risk_judge", expect.objectContaining({ assignedFlags: ["WRONG_DOSAGE"] })),
    );
    // the before/after preview shows the AUTHORED REFINEMENT now
    await screen.findByText(/AUTHORED REFINEMENT/);

    // attribute + save the assignment
    fireEvent.change(screen.getByLabelText(/Your handle/i), { target: { value: "sme@acme" } });
    fireEvent.change(screen.getByLabelText(/Rationale/i), { target: { value: "assign dosage lens" } });
    fireEvent.click(screen.getByRole("button", { name: /Save judge/i }));

    await waitFor(() => expect(putJudge).toHaveBeenCalledTimes(1));
    const [role, body, opts] = putJudge.mock.calls[0];
    expect(role).toBe("risk_judge");
    expect(body.assigned_flags).toEqual(["WRONG_DOSAGE"]);
    expect(opts).toMatchObject({ actor: "sme@acme", rationale: "assign dosage lens" });
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
  });

  it("S-BS-153: the save passes the ACTIVE agent so the server rosters the judge (the rail ticks)", async () => {
    render(<JudgeEditor role="risk_judge" agent="demo-clinical-agent" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    // the load already binds the active agent
    expect(getJudge.mock.calls[0]).toEqual(["risk_judge", { agent: "demo-clinical-agent" }]);
    fireEvent.click(screen.getByRole("button", { name: /Save judge/i }));
    await waitFor(() => expect(putJudge).toHaveBeenCalledTimes(1));
    // the active agent rides the PUT so the roster-add lands on the rail's agent
    expect(putJudge.mock.calls[0][2]).toMatchObject({ agent: "demo-clinical-agent" });
  });

  it("surfaces a 422 owner↔emit violation inline (never a silent pass)", async () => {
    putJudge.mockRejectedValueOnce(new Error("PUT /v1/judges/risk_judge → 422: owner↔emit: ..."));
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Save judge/i }));
    expect(await screen.findByText(/owner↔emit/)).toBeInTheDocument();
  });

  it("optimize: cost modal gates the PAID run, then renders a WIN Δ", async () => {
    optimizeJudge.mockResolvedValueOnce(
      deltaResult({ graded: 0.1, precision: 0.15, recall: 0.05 }),
    );
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();

    // the in-DOM cost modal (S-BS-69) gates the paid call — nothing fires until confirm
    fireEvent.click(screen.getByRole("button", { name: /^Optimize$/i }));
    expect(await screen.findByText(/Paid optimize run/i)).toBeInTheDocument();
    expect(optimizeJudge).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("optimize-confirm"));
    await waitFor(() => expect(optimizeJudge).toHaveBeenCalledWith("risk_judge", { confirm: true }));

    const delta = await screen.findByTestId("optimize-delta");
    expect(delta).toHaveAttribute("data-outcome", "win");
    expect(screen.getByText(/optimize improved this judge/i)).toBeInTheDocument();
    expect(screen.queryByTestId("optimize-loss-note")).toBeNull();
  });

  it("optimize: a ≤0 Δ renders EXPLICITLY as a loss, never hidden (R1)", async () => {
    optimizeJudge.mockResolvedValueOnce(
      deltaResult({ graded: -0.1, precision: -0.27, recall: -0.14 }),
    );
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^Optimize$/i }));
    fireEvent.click(await screen.findByTestId("optimize-confirm"));

    const delta = await screen.findByTestId("optimize-delta");
    expect(delta).toHaveAttribute("data-outcome", "loss");
    // the honest loss note is shown; no manufactured-win copy
    const note = screen.getByTestId("optimize-loss-note");
    expect(note).toHaveTextContent(/did not improve this judge/i);
    expect(screen.queryByText(/optimize improved this judge/i)).toBeNull();
  });

  it("optimize: cancelling the cost modal fires no paid call", async () => {
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Optimize$/i }));
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel$/i }));
    expect(optimizeJudge).not.toHaveBeenCalled();
  });
});
