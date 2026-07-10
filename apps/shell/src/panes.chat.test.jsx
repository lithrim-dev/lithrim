/* panes.chat.test.jsx — UAP-5b / R11: the live conversational loop in CenterPane.
   The composer streams POST /v1/chat (mocked chatStream); each SSE event renders
   inline — assistant text + a tool-result gen-UI part (the EXISTING verdict card,
   no new component). Mocks the whole bff.js surface so the scripted cards mount
   without a live BFF. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("./bff.js", () => ({
  runEval: vi.fn().mockResolvedValue({ composite: { verdict: "reject" }, council: { votes: [] } }),
  // COHORT-SUBSET-1: the cohort/subset grade the confirmPaidRun cohort branch calls.
  gradeCases: vi.fn().mockResolvedValue({ scorecard: { cases: [], n_cases: 0 }, summary: { grade_path: "in_process" } }),
  ingestPreview: vi.fn().mockResolvedValue({}),
  getRuns: vi.fn().mockResolvedValue({ runs: [] }),
  runEvalPack: vi.fn().mockResolvedValue({}),
  getCorpus: vi.fn().mockResolvedValue({ rows: [] }),
  // NARR-CHAT-LOOP: the show_case CaseCard self-fetches GET /v1/case — stub it so the rendered
  // card doesn't reject when a case_summary part streams in.
  getCase: vi.fn().mockResolvedValue({ case_id: "clinical_scribe_05", transcript: "…", expected_safety_flags: [] }),
  listCases: vi.fn().mockResolvedValue({ cases: [], count: 0 }),
  getOntology: vi.fn().mockResolvedValue({ flags: [], questions: [] }),
  putOntology: vi.fn().mockResolvedValue({}),
  // FAUTH-2: the registry's ContractBuilder fetches the live registered types on mount — stub it
  // so mounting the gen-UI registry under this whole-surface mock doesn't reach an undefined export.
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
  // PERSIST-CONV: CenterPane hydrates/persists/clears its thread via these — stub so the mount
  // hydrate is a clean empty thread (the existing scenarios are unchanged by it).
  getConversation: vi.fn().mockResolvedValue({ agent: "ws0_default", thread: [] }),
  putConversation: vi.fn().mockResolvedValue({ ok: true }),
  deleteConversation: vi.fn().mockResolvedValue({ ok: true, removed: false }),
  // UI-LOGIN-1 / SESSION-MENU-1: LeftRail (mounted via App) reads these for the session-menu
  // affordance — stub them so the rail renders without hitting an undefined export.
  hasStoredToken: vi.fn().mockReturnValue(false),
  logout: vi.fn(),
  signIn: vi.fn(),
  // CONNECT-AI-CONSOLIDATE-1: LeftRail statically imports ProviderSettings (2-section), which
  // imports these — stub so mounting the rail never reaches a real fetch.
  configProvider: vi.fn().mockResolvedValue({ ok: true, plane: "grading", provider: "openai", last_tested: "" }),
  getProviderStatus: vi.fn().mockResolvedValue({ planes: {} }),
  getModelCatalog: vi.fn().mockResolvedValue({ providers: { openai: [], anthropic: [], azure: { models: [], note: "" } } }),
  bindRole: vi.fn().mockResolvedValue({ ok: true }),
  getRoleBindings: vi.fn().mockResolvedValue({ roles: {}, connected_providers: [] }),
  getCouncilRoster: vi.fn().mockResolvedValue({ panel: [], reviewer_roster: null }),
  setCouncilRoster: vi.fn().mockResolvedValue({ status: "ok" }),
  // The loop under test: drive the onEvent callback with a scripted SSE stream.
  chatStream: vi.fn(async (_req, { onEvent } = {}) => {
    if (!onEvent) return;
    onEvent({ event: "assistant_delta", text: "Authoring the risk judge, then running a replay." });
    onEvent({
      event: "tool_result",
      part: {
        type: "tool-verdict_card",
        state: "output-available",
        output: { id: "run-1", verdict: "REJECT", confidence: "0.99", agreement: "3 / 3" },
      },
    });
    onEvent({ event: "done", cost_usd: 0.1, cost_label: "subscription-equivalent estimate" });
  }),
}));

import { CenterPane } from "./panes.jsx";
import App from "./app.jsx";
import { chatStream, runEval, gradeCases } from "./bff.js";

beforeEach(() => {
  chatStream.mockClear();
  runEval.mockClear();
  gradeCases.mockClear();
});

describe("CenterPane — the R11 conversational loop", () => {
  it("streams a chat turn: user msg + assistant text + the verdict card render inline", async () => {
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "Author a risk judge and run it" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(1));
    // ONB-0: the first send carries an empty history (no prior turns yet). NARR-CHAT-LOOP:
    // active_case rides the request (null when no case selected) so the loop targets the case on screen.
    expect(chatStream).toHaveBeenCalledWith(
      { message: "Author a risk judge and run it", agent: "ws0_default", history: [], active_case: null },
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );

    // the user's message echoes
    expect(await screen.findByText("Author a risk judge and run it")).toBeInTheDocument();
    // the streamed assistant text renders
    expect(await screen.findByText(/Authoring the risk judge/)).toBeInTheDocument();
    // the tool-result renders the EXISTING verdict card (no new component) — REJECT → "Flagged"
    expect(await screen.findByText("Flagged")).toBeInTheDocument();
  });

  it("CHATBIND-1: threads the ACTIVE (rail-selected) agent into chatStream, not ws0_default", async () => {
    // The shell half of the active-agent binding (S-BS-103): CenterPane's `agent` prop comes
    // from app.jsx's activeAgent; send() must POST it so the BFF loop scopes to the selected
    // case. Regression guard — if the prop threading regresses to the ws0_default default,
    // the chat would review the wrong case (the live dogfooding symptom).
    render(<CenterPane agent="imported_X" onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "show + review this case" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(1));
    expect(chatStream).toHaveBeenCalledWith(
      { message: "show + review this case", agent: "imported_X", history: [], active_case: null },
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );
  });

  it("NARR-CHAT-LOOP: threads the shared active case into chatStream + a case_summary part lifts it back", async () => {
    // The chat↔UI active-case is ONE thing: send() POSTs the UI-selected case so the loop targets
    // it; a show_case card carries the case_id it opened, which the shell lifts via onActiveCase.
    const onActiveCase = vi.fn();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-case_summary", state: "output-available", output: { agent: "ws0_default", case_id: "clinical_scribe_05" } } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane agent="ws0_default" activeCase="clinical_scribe_07" onActiveCase={onActiveCase}
      onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "open case 5" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(1));
    // UI → chat: the selected case rode the request
    expect(chatStream).toHaveBeenCalledWith(
      expect.objectContaining({ active_case: "clinical_scribe_07" }),
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );
    // chat → UI: the case the show_case card opened lifts back into the shared active case
    await waitFor(() => expect(onActiveCase).toHaveBeenCalledWith("clinical_scribe_05"));
  });

  it("streams the journey tool-parts and renders them inline via the existing registry (no new cards)", async () => {
    // UAP-5c: re-script the loop to stream the NEW journey cards as tool_result parts.
    // The chat pane renders them through the SAME type-agnostic renderTool path as the
    // verdict card above; per-type card rendering for all 9 tools is covered by
    // genui/registry.test.jsx. Here we assert the chat pane STREAMS a new journey part
    // and renders it inline — witnessed unambiguously by the audit_log card carrying the
    // streamed runId (the scripted-default audit_log has no run id, so it's chat-unique).
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "assistant_delta", text: "Reading the domain, editing a flag, reviewing runs." });
      onEvent({ event: "tool_result", part: { type: "tool-agent_editor", state: "output-available", output: { agent: "ws0_default" } } });
      onEvent({ event: "tool_result", part: { type: "tool-flag_editor", state: "output-available", output: { agent: "ws0_default" } } });
      onEvent({ event: "tool_result", part: { type: "tool-audit_log", state: "output-available", output: { runId: "run-1" } } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "subscription-equivalent estimate" });
    });
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "Walk the whole journey from scratch" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the chat streamed its narration, and the review_runs → audit_log part rendered the
    // EXISTING card inline carrying its streamed run id — none of the parts hit the fallback
    expect(await screen.findByText(/Reading the domain, editing a flag/)).toBeInTheDocument();
    expect(await screen.findByDisplayValue("run-1")).toBeInTheDocument();
    expect(screen.queryByText(/Unsupported component/)).toBeNull();
  });

  it("ONB-0: a 2nd send replays the prior turn as history (memory threads to the loop)", async () => {
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);

    // turn 1 — the default scripted stream yields assistant text "Authoring the risk judge…"
    fireEvent.change(ta, { target: { value: "my domain is radiology" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(1));
    await screen.findByText(/Authoring the risk judge/);

    // turn 2 — history must carry turn 1: the user msg + the streamed assistant text
    fireEvent.change(ta, { target: { value: "what did we just do?" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(2));

    const secondArgs = chatStream.mock.calls[1][0];
    expect(secondArgs.message).toBe("what did we just do?");
    expect(secondArgs.history).toEqual([
      { role: "user", content: "my domain is radiology" },
      { role: "assistant", content: "Authoring the risk judge, then running a replay." },
    ]);
  });

  it("opening the in-DOM cost modal exposes the human-only paid confirm (the agent cannot)", async () => {
    // CHAT-FRESH-GRADE-1: confirming the cost modal now grades FRESH (one cost-gated in_process
    // grade via runEval), not the old onRunEval(true) replay-as-paid path.
    runEval.mockResolvedValueOnce({ composite: { verdict: "approve" }, council: { votes: [] } });
    const onRunEval = vi.fn().mockResolvedValue();
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={onRunEval} onRunResult={vi.fn()} runStatus="idle" />);

    // the cost gate is the human's; trigger the modal via the composer's paid affordance
    fireEvent.click(screen.getByTitle(/Run a live, paid evaluation/i));
    const confirm = await screen.findByTestId("cost-confirm");
    fireEvent.click(confirm);
    // confirm fires ONE fresh, cost-gated grade — the modal is the only door, and the agent cannot.
    await waitFor(() =>
      expect(runEval).toHaveBeenCalledWith(expect.objectContaining({ in_process: true, confirm: true })),
    );
    expect(runEval).toHaveBeenCalledTimes(1);
  });
});

// CHATBIND-2: the chat drives the 3rd pane — a tool-open_artifact part is a DIRECTIVE (open +
// focus a tab), NOT a card; a run_result event lifts the chat's $0 run into the shell's shared
// runResult. The end-to-end (the focused tab renders THIS run) is app.chat.test.jsx (A4).
describe("CenterPane — CHATBIND-2: the chat drives the artifact pane", () => {
  it("A2 (non-vacuous): a tool-open_artifact part drives onOpenArtifact + a tiny affordance, never a card", async () => {
    const onOpenArtifact = vi.fn();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "assistant_delta", text: "Showing you the judge council." });
      onEvent({ event: "tool_result", part: { type: "tool-open_artifact", state: "output-available", output: { tab: "judges" } } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane onOpenArtifact={onOpenArtifact} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "show me the judge council" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the directive OPENED + FOCUSED the judges tab — FAILS if ignored
    await waitFor(() => expect(onOpenArtifact).toHaveBeenCalledWith("judges"));
    // it rendered a tiny NON-CARD affordance, NOT a gen-UI card and NOT the fallback (FAILS if
    // rendered inline via renderTool)
    expect(await screen.findByTestId("pane-directive")).toHaveTextContent(/Opened the Judges panel/);
    expect(screen.queryByText(/Unsupported component/)).toBeNull();
  });

  it("the shell guards an off-contract tab — a bogus directive does NOT open the pane", async () => {
    // defense-in-depth: the BFF tool already rejects an unknown tab, so a malformed/forged
    // frame can never reach openArtifact (which would setTab to an unknown -> titles[tab] crash).
    const onOpenArtifact = vi.fn();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-open_artifact", state: "output-available", output: { tab: "bogus" } } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane onOpenArtifact={onOpenArtifact} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "open bogus" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await screen.findByTestId("pane-directive"); // the turn settled
    expect(onOpenArtifact).not.toHaveBeenCalled(); // the guard held
  });

  it("D4: a run_result event lifts the chat's $0 run via onRunResult", async () => {
    const onRunResult = vi.fn();
    const record = { composite: { verdict: "reject" }, council: { votes: [{ vote: "reject" }] }, case_id: "c1" };
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "run_result", result: record });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane onOpenArtifact={vi.fn()} onRunResult={onRunResult} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "run a replay" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the lift threads the EXACT record up to the shell (byte-same to the manual Run-eval result)
    await waitFor(() => expect(onRunResult).toHaveBeenCalledWith(record));
  });
});

// CHATBIND-4: the consented live-run HAND-OFF — a tool-propose_live_run DIRECTIVE opens the in-DOM
// cost-confirm modal; the agent only PROPOSES, the human's confirm is the SOLE paid path.
describe("CenterPane — CHATBIND-4: the consented live-run hand-off", () => {
  it("a propose_live_run directive OPENS the cost modal but the agent NEVER spends (only the human's confirm does)", async () => {
    const onRunEval = vi.fn().mockResolvedValue();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "assistant_delta", text: "This case has no replay baseline — confirm a live run." });
      onEvent({ event: "tool_result", part: { type: "tool-propose_live_run", state: "output-available", output: {} } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={onRunEval} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "run it live" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the directive renders a tiny NON-CARD affordance AND opens the cost-confirm modal (the door)
    expect(await screen.findByTestId("paid-directive")).toHaveTextContent(/Surfaced the cost-confirm/);
    expect(await screen.findByTestId("cost-confirm")).toBeInTheDocument();
    // A-SAFE (NON-VACUOUS): opening the modal did NOT spend — onRunEval is untouched until the HUMAN confirms
    expect(onRunEval).not.toHaveBeenCalled();
    // the human's confirm is the ONLY thing that fires the paid run (and it grades FRESH —
    // CHAT-FRESH-GRADE-1: a cost-gated in_process grade, not the $0 replay).
    fireEvent.click(screen.getByTestId("cost-confirm"));
    await waitFor(() =>
      expect(runEval).toHaveBeenCalledWith(
        expect.objectContaining({ in_process: true, confirm: true }),
      ),
    );
  });

  it("FLOOR-VIS close-out: a tool-propose_run_all directive renders a trace, never the Unsupported fallback", async () => {
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "assistant_delta", text: "Confirm to grade the full cohort." });
      onEvent({ event: "tool_result", part: { type: "tool-propose_run_all", state: "output-available", output: {} } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);
    fireEvent.change(screen.getByPlaceholderText(/Ask Lithrim/i), { target: { value: "grade all cases" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    expect(await screen.findByTestId("paid-directive")).toHaveTextContent(/cost-confirm/i);
    expect(screen.queryByText(/Unsupported component/)).toBeNull();
  });
});

// CHAT-FRESH-GRADE-1: chat "run eval" GRADES FRESH (cost-confirmed) and the fresh grade shows up
// consistently in the chat verdict card + the report. The bug: confirming the cost modal showed
// NO fresh card in the chat thread (only the report lifted, via app.jsx), and the verdict could be
// a stale replay. The fix: confirmPaidRun runs ONE cost-gated in_process grade itself, appends a
// fresh verdict card to the chat thread, and lifts the SAME rec to the report — without app.jsx.
describe("CenterPane — CHAT-FRESH-GRADE-1: chat run-eval grades fresh + shows up", () => {
  const freshRec = {
    pipeline_run_id: "run_fresh_99",
    case_id: "run_002",
    composite: { verdict: "approve", active_findings: [] },
    council: { votes: [{ judge_role: "risk_judge", vote: "approve", confidence: 0.97 }] },
  };

  it("a propose_live_run confirm fires ONE fresh in_process grade + appends a fresh verdict card to the chat (NON-VACUOUS)", async () => {
    runEval.mockResolvedValueOnce(freshRec);
    const onRunEval = vi.fn().mockResolvedValue();
    const onRunResult = vi.fn();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "assistant_delta", text: "Confirm a fresh, paid grade for this case." });
      onEvent({ event: "tool_result", part: { type: "tool-propose_live_run", state: "output-available", output: {} } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(
      <CenterPane agent="ws0_default" activeCase="run_002" onActiveCase={vi.fn()}
        onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={onRunEval} onRunResult={onRunResult} runStatus="idle" />,
    );

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "run eval on this case" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // BEFORE the confirm: no fresh verdict card in the chat thread (non-vacuous baseline).
    await screen.findByTestId("paid-directive");
    expect(screen.queryByText("Passed")).toBeNull();

    // the human's confirm is the ONLY paid path; it grades FRESH (in_process+confirm), exactly once.
    fireEvent.click(screen.getByTestId("cost-confirm"));
    await waitFor(() => expect(runEval).toHaveBeenCalledTimes(1));
    expect(runEval).toHaveBeenCalledWith(
      expect.objectContaining({ agent: "ws0_default", case_id: "run_002", in_process: true, confirm: true }),
    );
    // EXACTLY ONCE — the fresh grade must not double-spend (no second runEval, no onRunEval(true)).
    expect(onRunEval).not.toHaveBeenCalled();

    // the fresh rec renders as a verdict card in the CHAT thread (the same verdict-card render).
    expect(await screen.findByText("Passed", { selector: ".tag" })).toBeInTheDocument(); // the verdict chip
    expect(screen.getAllByText("Result").length).toBeGreaterThan(0);
  });

  it("the appended chat card reflects the FRESH rec (APPROVE), not a prior/stale card", async () => {
    runEval.mockResolvedValueOnce(freshRec);
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-propose_live_run", state: "output-available", output: {} } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(
      <CenterPane agent="ws0_default" activeCase="run_002"
        onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
    );
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "grade it fresh" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    fireEvent.click(await screen.findByTestId("cost-confirm"));

    // the FRESH rec's verdict shows; the run id of the fresh grade is carried (not a stale id).
    expect(await screen.findByText("Passed", { selector: ".tag" })).toBeInTheDocument(); // the verdict chip
    expect(screen.getByText("run_fresh_99")).toBeInTheDocument();
  });

  it("onRunResult is called with the SAME fresh rec (chat ⇄ report consistency)", async () => {
    runEval.mockResolvedValueOnce(freshRec);
    const onRunResult = vi.fn();
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-propose_live_run", state: "output-available", output: {} } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(
      <CenterPane agent="ws0_default" activeCase="run_002"
        onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} onRunResult={onRunResult} runStatus="idle" />,
    );
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "grade it fresh" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    fireEvent.click(await screen.findByTestId("cost-confirm"));

    // the EXACT fresh rec lifts to the report — the chat card and the report show the same grade.
    await waitFor(() => expect(onRunResult).toHaveBeenCalledWith(freshRec));
  });
});

// UX-1 (S-BS-89): the chat surface defaults CLEAN — empty-state instead of the scripted
// 8-message preamble; the showcase is opt-in; "New evaluation" resets to a clean slate;
// live turns carry a neutral identity; cadence (auto-grow + autoscroll) is wired.
describe("CenterPane / Shell — UX-1: clean default + cadence + New-eval (S-BS-89)", () => {
  const props = { onOpenArtifact: vi.fn(), artifactOpen: false, onRunEval: vi.fn(), runStatus: "idle" };

  // revealing the opt-in showcase mounts the scripted FlagEditor, which self-fetches
  // GET /v1/ontology — stub fetch so the reveal is clean.
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ domain: "clinical", ontology_version: "clinical/1", severity_map: { block_at_or_above: 0.5, warn_above: 0, weights: {} }, flags: [] }),
      }),
    );
  });

  it("opens to a clean empty-state — no scripted demo content; 'Show example' reveals it", () => {
    render(<CenterPane {...props} />);
    // the real greeting is shown...
    expect(screen.getByText(/What do you want to evaluate\?/i)).toBeInTheDocument();
    // ...and NONE of the scripted preamble / fake header chips (A2)
    expect(screen.queryByText(/Scribe Agent v4/)).toBeNull();
    expect(screen.queryByText("Jordan")).toBeNull();
    expect(screen.queryByText(/sample case/)).toBeNull();

    // opt-in reveals the canned showcase (preamble + the fake header chips)
    fireEvent.click(screen.getByText(/Show example conversation/i));
    expect(screen.getByText(/sample case/)).toBeInTheDocument();
    expect(screen.getAllByText(/Example conversation/).length).toBeGreaterThan(0);
  });

  it("live turns use a neutral identity (You), never the scripted Jordan", async () => {
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "hello" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await screen.findByText(/Authoring the risk judge/);
    expect(screen.getAllByText("You").length).toBeGreaterThan(0);
    expect(screen.queryByText("Jordan")).toBeNull();
  });

  it("'New evaluation' resets the chat to a clean slate (App remounts CenterPane)", async () => {
    render(<App mode="shell" setMode={() => {}} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "reset me please" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    expect(await screen.findByText("reset me please")).toBeInTheDocument();

    fireEvent.click(screen.getByTitle("New evaluation"));
    // the live turn is gone and the empty-state is back
    expect(screen.queryByText("reset me please")).toBeNull();
    expect(screen.getByText(/What do you want to evaluate\?/i)).toBeInTheDocument();
  });

  it("composer auto-grows with input, capped at 200px", () => {
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    Object.defineProperty(ta, "scrollHeight", { configurable: true, value: 120 });
    fireEvent.change(ta, { target: { value: "a\nb\nc" } });
    expect(ta.style.height).toBe("120px");
    // grows up to the cap, then stops
    Object.defineProperty(ta, "scrollHeight", { configurable: true, value: 500 });
    fireEvent.change(ta, { target: { value: "a\nb\nc\nd\ne\nf\ng" } });
    expect(ta.style.height).toBe("200px");
  });

  it("autoscrolls to the latest turn on stream (scrollIntoView)", async () => {
    const spy = vi.spyOn(Element.prototype, "scrollIntoView");
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "scroll me" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await screen.findByText(/Authoring the risk judge/);
    expect(spy).toHaveBeenCalled();
  });
});

// CONV-UX-1 (W1): the tool_call wire event (loop.py:264) — formerly DROPPED by the shell —
// now renders an ordered activity timeline (a step per tool, running→done) and a non-static
// working indicator carrying the latest in-flight tool label, across the WHOLE in-flight window.
describe("CenterPane — CONV-UX-1 W1: thinking / working stages", () => {
  const props = { onOpenArtifact: vi.fn(), artifactOpen: false, onRunEval: vi.fn(), runStatus: "idle" };

  it("renders a tool_call as a human-labelled activity step (no longer dropped)", async () => {
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_call", name: "mcp__lithrim__get_agent", input: {} });
      onEvent({ event: "tool_call", name: "mcp__lithrim__author_judge", input: { role: "risk_judge" } });
      onEvent({ event: "assistant_delta", text: "Authored the risk judge." });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "create a risk judge" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the activity timeline mounted with the present-progressive labels mapped off the tool names
    const activity = await screen.findByTestId("activity");
    expect(activity).toHaveTextContent(/Reading the agent…/);
    expect(activity).toHaveTextContent(/Setting up the reviewer…/);
  });

  it("the working indicator shows the latest in-flight tool label during the turn (not a static 'Thinking…')", async () => {
    // hold the stream open after a tool_call so the indicator is asserted MID-FLIGHT (sending=true).
    let release;
    const gate = new Promise((r) => (release = r));
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_call", name: "mcp__lithrim__run_eval", input: {} });
      await gate; // the turn is still in flight here
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "run eval on this case" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // MID-FLIGHT: the non-static indicator shows the running tool's label, not a bare "Thinking…".
    // RUN-EVAL-FRESH-1: run_eval now SURFACES the cost-confirm (a fresh grade), so its chip reads
    // "Surfacing the cost-confirm…" — never "Running a $0 replay" (the stale-replay route is gone).
    const ind = await screen.findByTestId("working-indicator");
    expect(ind).toHaveTextContent(/Surfacing the cost-confirm…/);
    release();
    await waitFor(() => expect(screen.queryByTestId("working-indicator")).toBeNull());
  });
});

// CONV-UX-1 (W3): GenUI gating — dedup same-type cards, collapse `ondemand` passive reads to a
// compact affordance, and suppress ALL cards on an errored turn (the off-context-card-next-to-404
// the live drive hit must not recur).
describe("CenterPane — CONV-UX-1 W3: GenUI dedup / intent / error-guard", () => {
  const props = { onOpenArtifact: vi.fn(), artifactOpen: false, onRunEval: vi.fn(), runStatus: "idle" };

  it("dedups two same-type cards within a turn to ONE", async () => {
    // the VerdictCard renders synchronously from output (title "Verdict") — two same-type
    // parts in one turn must collapse to a single card.
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-verdict_card", state: "output-available", output: { id: "r1", verdict: "REJECT", confidence: "0.9", agreement: "3 / 3" }, show_intent: "auto" } });
      onEvent({ event: "tool_result", part: { type: "tool-verdict_card", state: "output-available", output: { id: "r1", verdict: "REJECT", confidence: "0.9", agreement: "3 / 3" }, show_intent: "auto" } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "run a replay" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // ONE card despite two same-type parts (and never the fallback)
    await waitFor(() => expect(screen.getAllByText("Result").length).toBe(1));
    expect(screen.queryByText(/Unsupported component/)).toBeNull();
  });

  it("collapses an `ondemand` passive read to a 'Show … ▸' affordance, expands on click", async () => {
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-audit_log", state: "output-available", output: { runId: "run-9" }, show_intent: "ondemand" } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "look around" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // a compact affordance, NOT a full card up front (the off-context Audit-trail card no longer pops)
    const od = await screen.findByTestId("ondemand-part");
    expect(od).toHaveTextContent(/Show audit trail ▸/);
  });

  it("suppresses ALL cards on an errored turn (no off-context card next to an error)", async () => {
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "tool_result", part: { type: "tool-audit_log", state: "output-available", output: { runId: "run-x" }, show_intent: "auto" } });
      onEvent({ event: "error", detail: "GET /v1/case?agent=ws0_default → 404" });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    });
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "create a risk judge" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // a calm, leak-free error line shows (friendlyError — never the raw verb/path/404)...
    expect(await screen.findByText(/⚠/)).toBeInTheDocument();
    expect(screen.queryByText(/404|\/v1\/case/)).toBeNull(); // the raw HTTP detail never leaks
    // ...and NO card (the audit_log part) rendered alongside it — the W3 error-guard held
    expect(screen.queryByDisplayValue("run-x")).toBeNull();
    expect(screen.queryByText(/Unsupported component/)).toBeNull();
  });
});

// COHORT-SUBSET-1 (feat/cohort-and-subset-ui): non-chat cohort triggers reach the SAME in-DOM
// cohort cost-confirm the chat's propose_run_all opens — via a window `lithrim:grade-cohort` event
// (the same CustomEvent bridge as lithrim:cmdk / connect-ai). detail.case_ids carries a subset
// (the Cases-browser "Run selected"); omitting it means ALL (the palette "Grade all"). The confirm
// is the ONLY paid path; it calls the subset-capable gradeCases and renders ScorecardCard inline.
describe("CenterPane — COHORT-SUBSET-1: non-chat cohort trigger + subset grade", () => {
  const props = { agent: "ws0_default", onOpenArtifact: vi.fn(), artifactOpen: false, onRunEval: vi.fn(), runStatus: "idle" };
  const fireCohort = (detail) => window.dispatchEvent(new CustomEvent("lithrim:grade-cohort", { detail }));

  it("a lithrim:grade-cohort event WITH case_ids opens the cohort cost-confirm; NO paid call before confirm", async () => {
    render(<CenterPane {...props} />);
    fireCohort({ case_ids: ["case_a", "case_c"] });
    // the SAME cohort modal the chat directive opens — but COHORT-SUBSET-1 last-mile: on a subset
    // the copy names the N selected cases (2 here), it does NOT read "Grade all cases".
    expect(await screen.findByText(/Grade 2 selected cases \(paid\)\?/i)).toBeInTheDocument();
    // credit-safety: NOTHING graded yet — the human hasn't confirmed
    expect(gradeCases).not.toHaveBeenCalled();
  });

  it("on confirm, a SUBSET cohort calls gradeCases WITH the case_ids + renders the scorecard inline", async () => {
    gradeCases.mockResolvedValueOnce({
      scorecard: { cases: [{ case_id: "case_a", verdict: "PASS", labeled: true, gold: [], caught: [], missed: [], spurious: [] }], n_cases: 1, n_labeled: 1, flag: { precision: 1, recall: 1 }, verdict_accuracy: "1/1" },
      summary: { grade_path: "in_process" },
    });
    render(<CenterPane {...props} />);
    fireCohort({ case_ids: ["case_a", "case_c"] });
    fireEvent.click(await screen.findByTestId("cost-confirm"));
    await waitFor(() =>
      expect(gradeCases).toHaveBeenCalledWith(
        expect.objectContaining({ agent: "ws0_default", in_process: true, case_ids: ["case_a", "case_c"] }),
      ),
    );
    // the SAME inline scorecard gen-UI the cohort path renders (ScorecardCard), scoped to the subset
    expect(await screen.findByText(/Scorecard · 1 case/)).toBeInTheDocument();
  });

  it("Grade all (no case_ids) calls gradeCases WITHOUT case_ids — the whole cohort", async () => {
    render(<CenterPane {...props} />);
    fireCohort({}); // palette "Grade all cases" — no subset
    fireEvent.click(await screen.findByTestId("cost-confirm"));
    await waitFor(() => expect(gradeCases).toHaveBeenCalledTimes(1));
    const arg = gradeCases.mock.calls[0][0];
    expect(arg.in_process).toBe(true);
    expect(arg.case_ids).toBeUndefined(); // all-cases grade passes no subset
  });
});
