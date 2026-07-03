/* app.statesync.test.jsx — STATE-SYNC (E1): the shared run + case state is per-agent, so the
   three panes (conversation, rail, side panel) must always agree on WHICH agent/run they show.
   Switching, deleting, or starting a NEW evaluation must clear the prior agent's run from the
   Report / Reviewers tabs — before E1 they bled across agents (reloadForWorkspace cleared on a
   workspace switch, but onSwitchAgent / onDeleteAgent / onNewEval did not). NON-VACUOUS: remove
   the resetEvalState() call from onNewEval and the lifted verdict survives, so this fails.

   Driven through the "+ New evaluation" affordance (always rendered, independent of the agent
   list) + the chat run-lift (the app.chat.test path) — resetEvalState() is synchronous and
   local, so the reset is observable even though createAgent's async tail is offline here. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("./bff.js", () => {
  const RECORD = {
    case_id: "imported_case_42",
    grade_path: "replay",
    composite: { verdict: "reject", stage_verdict: "BLOCK", score: 0.8, active_findings: [], grounded_adjustments: [] },
    calibration_check: { n_cases: 1, verdict_match_rate: "1/1", status: "ok", ece: "0.05" },
    council: { votes: [{ judge_role: "risk_judge", vote: "BLOCK", confidence: 0.91, model: "azure-gpt-4o", reason: "dosage not grounded" }] },
  };
  return {
    listAgents: vi.fn().mockResolvedValue({ agents: ["ws0_default"] }),
    createAgent: vi.fn().mockResolvedValue({}),
    deleteAgent: vi.fn().mockResolvedValue({}),
    deleteJudge: vi.fn().mockResolvedValue({}),
    runEval: vi.fn().mockResolvedValue(RECORD),
    getRuns: vi.fn().mockResolvedValue({ runs: [] }),
    getCorpus: vi.fn().mockResolvedValue({ rows: [] }),
    getOntology: vi.fn().mockResolvedValue({ flags: [], questions: [], severity_map: { block_at_or_above: 1, warn_above: 0, weights: {} } }),
    getAgent: vi.fn().mockResolvedValue({ name: "ws0_default", eval_profile: {} }),
    getJudges: vi.fn().mockResolvedValue({ judges: [], roles: [], validators: [] }),
    getJudge: vi.fn().mockResolvedValue({ role: "risk_judge", assigned_flags: [], questions: [] }),
    getAudit: vi.fn().mockResolvedValue({ records: [] }),
    getRunAudit: vi.fn().mockResolvedValue({}),
    getConversation: vi.fn().mockResolvedValue({ thread: [] }),
    putConversation: vi.fn().mockResolvedValue({}),
    deleteConversation: vi.fn().mockResolvedValue({}),
    hasStoredToken: vi.fn().mockReturnValue(false),
    logout: vi.fn(),
    signIn: vi.fn(),
    configProvider: vi.fn().mockResolvedValue({ ok: true }),
    getProviderStatus: vi.fn().mockResolvedValue({ planes: {} }),
    getModelCatalog: vi.fn().mockResolvedValue({ providers: { openai: [], anthropic: [], azure: { models: [], note: "" } } }),
    bindRole: vi.fn().mockResolvedValue({ ok: true }),
    getRoleBindings: vi.fn().mockResolvedValue({ roles: {}, connected_providers: [] }),
    getCouncilRoster: vi.fn().mockResolvedValue({ panel: [], reviewer_roster: null }),
    setCouncilRoster: vi.fn().mockResolvedValue({ status: "ok" }),
    chatStream: vi.fn(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "assistant_delta", text: "Running a $0 replay and showing the council." });
      onEvent({ event: "run_result", result: RECORD });
      onEvent({ event: "tool_result", part: { type: "tool-open_artifact", state: "output-available", output: { tab: "judges" } } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
    }),
  };
});

import App from "./app.jsx";

async function liftRunViaChat() {
  const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
  fireEvent.change(ta, { target: { value: "run a $0 replay and show me the judge council" } });
  fireEvent.click(screen.getByTestId("chat-send"));
  // the lifted run renders its realized vote in the focused Reviewers tab (the side panel)
  expect(await screen.findByText("Risk reviewer")).toBeInTheDocument();
}

describe("STATE-SYNC (E1) — the panes don't bleed a prior agent's run/case", () => {
  it("starting a new evaluation clears the lifted run from the side panel", async () => {
    render(<App mode="shell" setMode={() => {}} />);
    await liftRunViaChat();

    // "+ New evaluation" switches to a fresh agent — the prior run must not bleed into the panes
    fireEvent.click(screen.getByLabelText("New evaluation"));

    await waitFor(() => expect(screen.queryByText("Risk reviewer")).not.toBeInTheDocument());
    // the side panel returns to its honest empty state instead of the stale verdict
    expect(screen.getByText(/No run yet/i)).toBeInTheDocument();
  });
});
