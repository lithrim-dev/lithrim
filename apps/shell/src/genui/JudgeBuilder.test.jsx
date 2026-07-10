/* JudgeBuilder.test.jsx — PHASE2-C: the inline "Create reviewer" authoring card mints a NEW
   first-class judge over the active pack's taxonomy snapshot (POST /v1/judges), audited.

   Covers the SPINE/CONTAINMENT invariant (the human's Save is the SOLE write — surfacing the
   card writes nothing), the owner↔emit guard (owned ⊆ lens, mirroring JudgeEditor), the ⚠
   no-logprobs pool hint (MR-1c consistency), an inline 422 detail (not swallowed), and the
   absolute-2 / one-strike honesty note (PROBE Q3/Q4). Mirrors CriterionBuilder.test.jsx. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

// JudgeBuilder reads the active pack's codes via GET /v1/ontology and the model pool via
// GET /v1/models, then mints via POST /v1/judges (createJudge) before firing onResult — mock
// all three so mounting never reaches a real fetch (mirrors CriterionBuilder/inputs.test.jsx).
vi.mock("../bff.js", () => ({
  getOntology: vi.fn().mockResolvedValue({
    domain: "support_ticket_qa",
    flags: [
      { flag: "MISSED_ESCALATION", tier: "TIER_1" },
      { flag: "WRONG_RESOLUTION", tier: "TIER_2" },
      { flag: "TONE_VIOLATION", tier: "TIER_3" },
    ],
  }),
  listModels: vi.fn().mockResolvedValue({
    models: [
      { id: "grader-gpt4o", provider: "openai", model: "gpt-4o", capabilities: { logprobs: true } },
      { id: "claude-native", provider: "anthropic", model: "claude-3-7", capabilities: { logprobs: false } },
    ],
  }),
  bindModel: vi.fn().mockResolvedValue({ status: "ok" }),
  createJudge: vi.fn().mockResolvedValue({
    role: "escalation_judge",
    lens_codes: ["MISSED_ESCALATION", "WRONG_RESOLUTION"],
    owned_codes: ["MISSED_ESCALATION"],
    model: "grader-gpt4o",
    bound_roles: ["escalation_judge"],
    audit_id: "aud-1",
  }),
}));

import JudgeBuilder from "./JudgeBuilder.jsx";
import { createJudge, listModels } from "../bff.js";

// drive the card to a Save-ready state: type a role, pick lens codes, optionally owned codes.
async function setup(props = {}) {
  const onResult = vi.fn();
  render(<JudgeBuilder agent="support-1" onResult={onResult} {...props} />);
  // the lens codes load from the ontology — wait for the first option to paint.
  await screen.findByLabelText(/lens MISSED_ESCALATION/i);
  return { onResult };
}

describe("JudgeBuilder — PHASE2-C inline create-judge over the snapshot", () => {
  it("A: renders role / lens / owned / model / prompt fields + the absolute-2 honesty note", async () => {
    await setup();
    expect(screen.getByLabelText("reviewer id")).toBeInTheDocument();
    // lens codes from the ontology
    expect(screen.getByLabelText(/lens MISSED_ESCALATION/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/lens WRONG_RESOLUTION/i)).toBeInTheDocument();
    // owned codes (the one-strike owner column)
    expect(screen.getByLabelText(/own MISSED_ESCALATION/i)).toBeInTheDocument();
    // model pick-from-pool + the role-prompt seed
    expect(screen.getByLabelText("judge model")).toBeInTheDocument();
    expect(screen.getByLabelText("role prompt seed")).toBeInTheDocument();
    // the NON-NEGOTIABLE absolute-2 / one-strike honesty note, rendered inline verbatim
    expect(
      screen.getByText(/corroboration is an absolute 2 votes/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Solo one-strike authority for a newly-owned code activates on the next graded run/i),
    ).toBeInTheDocument();
  });

  it("B: the owner↔emit guard — owning a code NOT in the lens is blocked/flagged (Save guarded)", async () => {
    createJudge.mockClear();
    await setup();
    fireEvent.change(screen.getByLabelText("reviewer id"), { target: { value: "escalation_judge" } });
    // own a code WITHOUT adding it to the lens → owner⊄lens, the guard fires
    fireEvent.click(screen.getByLabelText(/own MISSED_ESCALATION/i));
    expect(screen.getByTestId("owner-emit-guard")).toBeInTheDocument();
    const save = screen.getByRole("button", { name: /Create reviewer/i });
    expect(save).toBeDisabled();
    fireEvent.click(save);
    expect(createJudge).not.toHaveBeenCalled();
  });

  it("C: Save → createJudge with the entered {role, lens_codes, owned_codes, model_id?, rationale}", async () => {
    createJudge.mockClear();
    const { onResult } = await setup();
    fireEvent.change(screen.getByLabelText("reviewer id"), { target: { value: "escalation_judge" } });
    fireEvent.change(screen.getByLabelText("audit rationale"), { target: { value: "support escalations" } });
    // lens: two codes; own one of them (⊆ lens → guard clear)
    fireEvent.click(screen.getByLabelText(/lens MISSED_ESCALATION/i));
    fireEvent.click(screen.getByLabelText(/lens WRONG_RESOLUTION/i));
    fireEvent.click(screen.getByLabelText(/own MISSED_ESCALATION/i));
    // pick a model from the pool
    fireEvent.change(screen.getByLabelText("judge model"), { target: { value: "grader-gpt4o" } });

    // SPINE INVARIANT (UI side): nothing is written until the human clicks Create.
    expect(createJudge).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Create reviewer/i }));

    await waitFor(() => expect(createJudge).toHaveBeenCalledTimes(1));
    const [body] = createJudge.mock.calls[0];
    expect(body).toMatchObject({
      role: "escalation_judge",
      lens_codes: ["MISSED_ESCALATION", "WRONG_RESOLUTION"],
      owned_codes: ["MISSED_ESCALATION"],
      model_id: "grader-gpt4o",
      rationale: "support escalations",
    });
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
  });

  it("D: a 422 {detail} from createJudge renders inline (not swallowed); onResult NOT fired", async () => {
    createJudge.mockClear();
    createJudge.mockRejectedValueOnce(new Error("POST /v1/judges → 422: role collision: escalation_judge already exists"));
    const { onResult } = await setup();
    fireEvent.change(screen.getByLabelText("reviewer id"), { target: { value: "escalation_judge" } });
    fireEvent.change(screen.getByLabelText("audit rationale"), { target: { value: "dup" } });
    fireEvent.click(screen.getByLabelText(/lens MISSED_ESCALATION/i));
    fireEvent.click(screen.getByRole("button", { name: /Create reviewer/i }));

    await waitFor(() => expect(screen.getByText(/role collision/i)).toBeInTheDocument());
    expect(onResult).not.toHaveBeenCalled();
  });

  it("E: onResult fires ONLY on a successful write (the SPINE discipline)", async () => {
    createJudge.mockClear();
    const { onResult } = await setup();
    // an empty lens is inadmissible → Save guarded, no write, no onResult.
    fireEvent.change(screen.getByLabelText("reviewer id"), { target: { value: "escalation_judge" } });
    expect(screen.getByRole("button", { name: /Create reviewer/i })).toBeDisabled();
    expect(onResult).not.toHaveBeenCalled();

    // add a lens code → admissible → write → onResult fires exactly once.
    fireEvent.change(screen.getByLabelText("audit rationale"), { target: { value: "ok" } });
    fireEvent.click(screen.getByLabelText(/lens MISSED_ESCALATION/i));
    fireEvent.click(screen.getByRole("button", { name: /Create reviewer/i }));
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
    expect(createJudge).toHaveBeenCalledTimes(1);
  });

  it("F: picking a logprobs:false pool model surfaces the ⚠ no-logprobs hint (MR-1c)", async () => {
    await setup();
    expect(listModels).toHaveBeenCalled();
    // pick the anthropic pool entry (logprobs:false)
    fireEvent.change(screen.getByLabelText("judge model"), { target: { value: "claude-native" } });
    const hint = screen.getByTestId("judge-model-logprobs-hint");
    expect(within(hint).getByText(/confidence signal/i)).toBeInTheDocument();
  });
});
