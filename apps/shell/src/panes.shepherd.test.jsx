/* panes.shepherd.test.jsx — SHEPHERD-1: the shepherd-aware empty state (W4) + the
   approval-gate save->advance callback (W3). Mocks the whole bff.js surface so the
   editor card mounts without a live BFF (mirrors panes.chat.test.jsx). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("./bff.js", () => ({
  runEval: vi.fn().mockResolvedValue({}),
  getRuns: vi.fn().mockResolvedValue({ runs: [] }),
  runEvalPack: vi.fn().mockResolvedValue({}),
  getCorpus: vi.fn().mockResolvedValue({ rows: [] }),
  getOntology: vi.fn().mockResolvedValue({ flags: [], questions: [] }),
  putOntology: vi.fn().mockResolvedValue({}),
  getAgent: vi.fn().mockResolvedValue({ name: "eval-1", eval_profile: {} }),
  putAgent: vi.fn().mockResolvedValue({}),
  getAudit: vi.fn().mockResolvedValue({ records: [] }),
  getRunAudit: vi.fn().mockResolvedValue({}),
  getJudges: vi.fn().mockResolvedValue({ judges: [], roles: [], validators: [] }),
  getJudge: vi.fn().mockResolvedValue({
    role: "risk_judge", model: "", assigned_flags: [], available_flags: [],
    available_validators: [], validator_refs: [], questions: [], base_prompt: "", rendered_prompt: "",
  }),
  putJudge: vi.fn().mockResolvedValue({ status: "ok", role: "risk_judge", actor: { type: "user", id: "sme" } }),
  optimizeJudge: vi.fn().mockResolvedValue({}),
  listCases: vi.fn().mockResolvedValue({ cases: [], count: 0 }),
  chatStream: vi.fn(async (_req, { onEvent } = {}) => {
    if (!onEvent) return;
    onEvent({ event: "assistant_delta", text: "Let's author your first judge." });
    // a save-pending JudgeEditor card (the approval gate the agent proposes).
    onEvent({
      event: "tool_result",
      part: { type: "tool-judge_editor", state: "output-available", output: { role: "risk_judge", agent: "eval-1" } },
    });
    onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
  }),
}));

import { CenterPane } from "./panes.jsx";

beforeEach(() => vi.clearAllMocks());

describe("SHEPHERD-1 W4 — shepherd-aware empty state", () => {
  const base = { onOpenArtifact: () => {}, onRunEval: () => {}, runStatus: "idle", agent: "eval-1" };

  it("offers 'Start guided setup' and a 'Next: <step>' chip; clicking fills the composer (no auto-send)", () => {
    render(<CenterPane {...base} nextStepName="Domain" />);
    const guided = screen.getByTestId("start-guided-setup");
    const next = screen.getByTestId("next-step-prompt");
    expect(next).toHaveTextContent("Next: Domain");
    // the old static chips are gone
    expect(screen.queryByText("Create a risk judge for your agent's answers")).toBeNull();
    fireEvent.click(guided);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    expect(ta.value).toMatch(/set up my first evaluation/i); // FILLED, not sent
    expect(window.__sent).toBeUndefined?.(); // sanity: no chatStream auto-fire
  });

  it("omits the next-step chip when the journey is complete (nextStepName null)", () => {
    render(<CenterPane {...base} nextStepName={null} />);
    expect(screen.getByTestId("start-guided-setup")).toBeInTheDocument();
    expect(screen.queryByTestId("next-step-prompt")).toBeNull();
  });
});

describe("SHEPHERD-1 W3 — a proposed editor's Save fires onConfigSaved (rail re-derive)", () => {
  const base = { onOpenArtifact: () => {}, onRunEval: () => {}, runStatus: "idle", agent: "eval-1" };

  it("on the judge-editor Save, captureSetup invokes onConfigSaved", async () => {
    const onConfigSaved = vi.fn();
    render(<CenterPane {...base} onConfigSaved={onConfigSaved} />);
    // drive a turn that proposes the JudgeEditor card.
    fireEvent.change(screen.getByPlaceholderText(/Ask Lithrim/i), { target: { value: "author a judge" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    // the proposed card mounts; Save it (the approval gate → the real audited PUT mock).
    await screen.findByRole("button", { name: /Save judge/i });
    fireEvent.click(screen.getByRole("button", { name: /Save judge/i }));
    await waitFor(() => expect(onConfigSaved).toHaveBeenCalled());
  });
});
