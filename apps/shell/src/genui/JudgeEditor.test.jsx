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
}));

import JudgeEditor from "./JudgeEditor.jsx";
import { getJudge, putJudge } from "../bff.js";

beforeEach(() => {
  getJudge.mockClear();
  putJudge.mockClear();
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

  it("surfaces a 422 owner↔emit violation inline (never a silent pass)", async () => {
    putJudge.mockRejectedValueOnce(new Error("PUT /v1/judges/risk_judge → 422: owner↔emit: ..."));
    render(<JudgeEditor role="risk_judge" />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Save judge/i }));
    expect(await screen.findByText(/owner↔emit/)).toBeInTheDocument();
  });
});
