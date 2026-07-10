/* panes.casetarget.test.jsx — CHAT-CASE-TARGET-1: the chat-named case is the case that gets graded.

   The bug (CONFIRMED live): the user types "run a live eval on run_001_fabricates" while the client
   activeCase is the stale top-bar selection (run_002_faithful). The agent calls
   run_eval{case_id:"run_001_fabricates"} → the BFF sets ctx.active_case but emitted a directive with
   an EMPTY output, so confirmPaidRun fell back to the stale client activeCase → graded run_002.

   The fix: the directive carries the targeted case_id; the shell syncs activeCase to it (mirroring
   the show_case lift) AND confirmPaidRun grades paid.caseId || activeCase. A-SAFE: the case_id is a
   SELECTOR; the human's in-DOM confirm is STILL the only paid path. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("./bff.js", () => ({
  runEval: vi.fn().mockResolvedValue({ composite: { verdict: "reject" }, council: { votes: [] } }),
  getRuns: vi.fn().mockResolvedValue({ runs: [] }),
  runEvalPack: vi.fn().mockResolvedValue({}),
  getCorpus: vi.fn().mockResolvedValue({ rows: [] }),
  getCase: vi.fn().mockResolvedValue({ case_id: "x", transcript: "…", expected_safety_flags: [] }),
  listCases: vi.fn().mockResolvedValue({ cases: [], count: 0 }),
  getOntology: vi.fn().mockResolvedValue({ flags: [], questions: [] }),
  putOntology: vi.fn().mockResolvedValue({}),
  getGroundingContractTypes: vi.fn().mockResolvedValue({ contract_types: ["presence_check"], pack: "_core" }),
  getAgent: vi.fn().mockResolvedValue({ name: "ws0_default", eval_profile: {} }),
  putAgent: vi.fn().mockResolvedValue({}),
  getAudit: vi.fn().mockResolvedValue({ records: [] }),
  getRunAudit: vi.fn().mockResolvedValue({}),
  getJudges: vi.fn().mockResolvedValue({ judges: [], roles: [], validators: [] }),
  getJudge: vi.fn().mockResolvedValue({
    role: "risk_judge", model: "", assigned_flags: [], available_flags: [],
    available_validators: [], validator_refs: [], questions: [], base_prompt: "", rendered_prompt: "",
  }),
  putJudge: vi.fn().mockResolvedValue({}),
  optimizeJudge: vi.fn().mockResolvedValue({}),
  getConversation: vi.fn().mockResolvedValue({ agent: "ws0_default", thread: [] }),
  putConversation: vi.fn().mockResolvedValue({ ok: true }),
  deleteConversation: vi.fn().mockResolvedValue({ ok: true, removed: false }),
  hasStoredToken: vi.fn().mockReturnValue(false),
  logout: vi.fn(),
  signIn: vi.fn(),
  configProvider: vi.fn().mockResolvedValue({ ok: true, plane: "grading", provider: "openai", last_tested: "" }),
  getProviderStatus: vi.fn().mockResolvedValue({ planes: {} }),
  getModelCatalog: vi.fn().mockResolvedValue({ providers: { openai: [], anthropic: [], azure: { models: [], note: "" } } }),
  bindRole: vi.fn().mockResolvedValue({ ok: true }),
  getRoleBindings: vi.fn().mockResolvedValue({ roles: {}, connected_providers: [] }),
  getCouncilRoster: vi.fn().mockResolvedValue({ panel: [], reviewer_roster: null }),
  setCouncilRoster: vi.fn().mockResolvedValue({ status: "ok" }),
  chatStream: vi.fn(async () => {}),
}));

import { CenterPane } from "./panes.jsx";
import { chatStream, runEval } from "./bff.js";

beforeEach(() => {
  chatStream.mockClear();
  runEval.mockClear();
});

// the freshRec the cost-gated grade resolves with (so confirm completes cleanly)
const freshRec = {
  pipeline_run_id: "run_fresh_target",
  case_id: "run_001_fabricates",
  composite: { verdict: "reject", active_findings: [] },
  council: { votes: [{ judge_role: "risk_judge", vote: "reject", confidence: 0.99 }] },
};

describe("CenterPane — CHAT-CASE-TARGET-1: the directive's case is the case graded", () => {
  it("THE HEADLINE: a propose_live_run carrying case_id syncs activeCase + confirm grades THAT case (not the stale one)", async () => {
    // client is on the STALE top-bar selection run_002_faithful; the chat names run_001_fabricates.
    runEval.mockResolvedValueOnce(freshRec);
    const onActiveCase = vi.fn();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "assistant_delta", text: "Surfacing the cost-confirm for run_001_fabricates." });
      onEvent({ event: "tool_result", part: { type: "tool-propose_live_run", state: "output-available", output: { case_id: "run_001_fabricates" } } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(
      <CenterPane agent="ws0_default" activeCase="run_002_faithful" onActiveCase={onActiveCase}
        onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
    );

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "run a live eval on run_001_fabricates" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the directive synced the UI to the TARGETED case (mirrors the show_case lift) AND opened the modal
    await waitFor(() => expect(onActiveCase).toHaveBeenCalledWith("run_001_fabricates"));
    expect(await screen.findByTestId("cost-confirm")).toBeInTheDocument();
    // A-SAFE: opening the modal did NOT spend — runEval untouched until the HUMAN confirms
    expect(runEval).not.toHaveBeenCalled();

    // the human's confirm grades the DIRECTIVE's case (run_001), NOT the stale client activeCase (run_002)
    fireEvent.click(screen.getByTestId("cost-confirm"));
    await waitFor(() => expect(runEval).toHaveBeenCalledTimes(1));
    expect(runEval).toHaveBeenCalledWith(
      expect.objectContaining({ agent: "ws0_default", case_id: "run_001_fabricates", in_process: true, confirm: true }),
    );
    // the WRONG case was never the spend target
    expect(runEval).not.toHaveBeenCalledWith(expect.objectContaining({ case_id: "run_002_faithful" }));
  });

  it("NON-VACUOUS back-compat: an EMPTY-output directive grades the client activeCase, no onActiveCase sync (the TopBar path)", async () => {
    runEval.mockResolvedValueOnce({ composite: { verdict: "approve" }, council: { votes: [] } });
    const onActiveCase = vi.fn();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-propose_live_run", state: "output-available", output: {} } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(
      <CenterPane agent="ws0_default" activeCase="run_002_faithful" onActiveCase={onActiveCase}
        onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
    );

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "run it live" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    fireEvent.click(await screen.findByTestId("cost-confirm"));
    await waitFor(() => expect(runEval).toHaveBeenCalledTimes(1));
    // an empty directive carries no case → no sync, and confirm falls back to the client activeCase
    expect(onActiveCase).not.toHaveBeenCalled();
    expect(runEval).toHaveBeenCalledWith(
      expect.objectContaining({ agent: "ws0_default", case_id: "run_002_faithful", in_process: true, confirm: true }),
    );
  });

  it("REGRESSION: the TopBar 'Run live' button (no directive) grades activeCase unchanged", async () => {
    runEval.mockResolvedValueOnce({ composite: { verdict: "approve" }, council: { votes: [] } });
    const onActiveCase = vi.fn();
    render(
      <CenterPane agent="ws0_default" activeCase="run_002_faithful" onActiveCase={onActiveCase}
        onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
    );

    // the TopBar paid affordance opens the modal directly (no directive, so no paid.caseId)
    fireEvent.click(screen.getByTitle(/Run a live, paid evaluation/i));
    fireEvent.click(await screen.findByTestId("cost-confirm"));
    await waitFor(() => expect(runEval).toHaveBeenCalledTimes(1));
    expect(runEval).toHaveBeenCalledWith(
      expect.objectContaining({ agent: "ws0_default", case_id: "run_002_faithful", in_process: true, confirm: true }),
    );
    expect(onActiveCase).not.toHaveBeenCalled();
  });

  it("CHAT-FRESH-GRADE-1 still holds: the confirm appends a fresh verdict card + lifts onRunResult once (no double-spend)", async () => {
    runEval.mockResolvedValueOnce(freshRec);
    const onRunResult = vi.fn();
    const onRunEval = vi.fn().mockResolvedValue();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-propose_live_run", state: "output-available", output: { case_id: "run_001_fabricates" } } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(
      <CenterPane agent="ws0_default" activeCase="run_002_faithful" onActiveCase={vi.fn()}
        onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={onRunEval} onRunResult={onRunResult} runStatus="idle" />,
    );

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "grade run_001 fresh" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    fireEvent.click(await screen.findByTestId("cost-confirm"));

    // the fresh rec renders inline as a verdict card AND lifts to the report — ONE spend (no onRunEval).
    expect(await screen.findByText("Flagged", { selector: ".tag" })).toBeInTheDocument(); // the verdict chip
    await waitFor(() => expect(onRunResult).toHaveBeenCalledWith(freshRec));
    expect(runEval).toHaveBeenCalledTimes(1);
    expect(onRunEval).not.toHaveBeenCalled();
  });
});

// FINDING #2 (UI-pass 2026-07-04): "Explore case" used to open the Case tab even with NO case
// selected — the pane then rendered the agent's default case under a "No case selected" header
// (two case states silently out of sync). With nothing selected it now opens the Cases BROWSER
// so the user picks explicitly; with a selection it still jumps straight to that case.
describe("CenterPane — Explore case targets the browser when no case is selected", () => {
  it("no active case → Explore case opens the Cases tab (the browser)", () => {
    const onOpenArtifact = vi.fn();
    render(
      <CenterPane agent="ws0_default" activeCase={null} onActiveCase={vi.fn()}
        onOpenArtifact={onOpenArtifact} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
    );
    fireEvent.click(screen.getByText("Explore case"));
    expect(onOpenArtifact).toHaveBeenCalledWith("corpus");
  });

  it("an active case → Explore case still opens that case directly", () => {
    const onOpenArtifact = vi.fn();
    render(
      <CenterPane agent="ws0_default" activeCase="run_001_fabricates" onActiveCase={vi.fn()}
        onOpenArtifact={onOpenArtifact} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
    );
    fireEvent.click(screen.getByText("Explore case"));
    expect(onOpenArtifact).toHaveBeenCalledWith("case");
  });
});
