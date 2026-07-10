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
  listCases: vi.fn().mockResolvedValue({
    cases: [
      { case_id: "cv_mts_101", labeled: true },
      { case_id: "cv_mts_102", labeled: true },
      { case_id: "cv_mts_103", labeled: false },
    ],
    count: 3,
  }),
}));

import JudgeEditor from "./JudgeEditor.jsx";
import { getJudge, putJudge, optimizeJudge, listCases } from "../bff.js";

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
  listCases.mockClear();
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
    fireEvent.change(screen.getByLabelText(/Your name/i), { target: { value: "sme@acme" } });
    fireEvent.change(screen.getByLabelText(/Reason/i), { target: { value: "assign dosage lens" } });
    fireEvent.click(screen.getByRole("button", { name: /Save judge/i }));

    await waitFor(() => expect(putJudge).toHaveBeenCalledTimes(1));
    const [role, body, opts] = putJudge.mock.calls[0];
    expect(role).toBe("risk_judge");
    expect(body.assigned_flags).toEqual(["WRONG_DOSAGE"]);
    expect(opts).toMatchObject({ actor: "sme@acme", rationale: "assign dosage lens" });
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
  });

  it("VOTE-MODEL-2: shows the model the reviewer actually grades on when bound via Providers (override field blank)", async () => {
    getJudge.mockResolvedValueOnce({
      ...SUMMARY, role: "risk_judge", model: "",
      effective_model: "Mistral-Large-3", effective_provider: "azure", model_source: "binding",
    });
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    // the effective grading model surfaces even though the editable override is empty
    const eff = screen.getByTestId("je-effective-model");
    expect(eff).toHaveTextContent(/azure · Mistral-Large-3/);
    expect(eff).toHaveTextContent(/Providers/i); // tells the user WHERE it was set
  });

  it("PROMPT-EDIT-1: edits the reviewer prompt and sends role_prompt in the PUT (SME, no code)", async () => {
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    const ta = screen.getByTestId("je-role-prompt");
    expect(ta).toHaveValue("SEED PROMPT BASE"); // seeded from base_prompt
    fireEvent.change(ta, { target: { value: "Flag INTENT_ERASURE when the note drops the patient's stated intent." } });
    fireEvent.click(screen.getByRole("button", { name: /Save judge/i }));
    await waitFor(() => expect(putJudge).toHaveBeenCalledTimes(1));
    expect(putJudge.mock.calls[0][1]).toMatchObject({
      role_prompt: "Flag INTENT_ERASURE when the note drops the patient's stated intent.",
    });
  });

  it("PROMPT-EDIT-1: a lens-only save does NOT resend the prompt (no spurious prompt edit)", async () => {
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Save judge/i }));
    await waitFor(() => expect(putJudge).toHaveBeenCalledTimes(1));
    expect(putJudge.mock.calls[0][1].role_prompt).toBeUndefined();
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
    expect(await screen.findByText(/owner↔emit/i)).toBeInTheDocument();
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

  it("optimize-on-subset: no case selected → whole-workspace (case_ids absent, $0 until confirm)", async () => {
    optimizeJudge.mockResolvedValueOnce(deltaResult({ graded: 0.1 }));
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    // the case picker lists the workspace cases ($0 read)
    expect(await screen.findByTestId("optimize-case-cv_mts_101")).toBeInTheDocument();
    // no selection → the optimize call carries NO caseIds (today's whole-workspace behaviour)
    fireEvent.click(screen.getByRole("button", { name: /^Optimize$/i }));
    fireEvent.click(await screen.findByTestId("optimize-confirm"));
    await waitFor(() => expect(optimizeJudge).toHaveBeenCalledWith("risk_judge", { confirm: true }));
  });

  it("optimize-on-subset: chosen cases scope the optimize (caseIds threaded, still gated)", async () => {
    optimizeJudge.mockResolvedValueOnce(deltaResult({ graded: 0.1 }));
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    // pick two cases from the picker
    fireEvent.click(await screen.findByTestId("optimize-case-cv_mts_101"));
    fireEvent.click(screen.getByTestId("optimize-case-cv_mts_102"));
    // still paid-gated: nothing fires until confirm
    fireEvent.click(screen.getByRole("button", { name: /^Optimize$/i }));
    expect(optimizeJudge).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByTestId("optimize-confirm"));
    await waitFor(() =>
      expect(optimizeJudge).toHaveBeenCalledWith("risk_judge", {
        confirm: true,
        caseIds: ["cv_mts_101", "cv_mts_102"],
      }),
    );
  });
});
