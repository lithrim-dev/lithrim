/* app.chat.test.jsx — CHATBIND-2 (A4, end-to-end): a chat-driven $0 run + a pane directive
   reach the FOCUSED artifact tab. The conversation streams a run_result (lifted into the
   shared runResult via App.onRunResult) + a tool-open_artifact("judges") directive (which
   opens + focuses the Judge council tab); the shell then renders THIS run's realized votes
   in that tab — the fully chat-driven demo, offline ($0). Non-vacuous: if the directive were
   ignored or the run not lifted, the votes would not appear in the focused tab. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// the bff.js mock factory is hoisted, so RECORD lives INSIDE it (a top-level const would be
// referenced before init). It is the chat's $0 replay record — complete enough for BOTH the
// Report and Judge tabs so a transient render on the default 'report' tab can't crash.
vi.mock("./bff.js", () => {
  const RECORD = {
    case_id: "imported_case_42",
    grade_path: "replay",
    composite: {
      verdict: "reject",
      stage_verdict: "BLOCK",
      score: 0.8,
      active_findings: [],
      grounded_adjustments: [],
    },
    calibration_check: { n_cases: 1, verdict_match_rate: "1/1", status: "ok", ece: "0.05" },
    council: {
      votes: [
        { judge_role: "risk_judge", vote: "BLOCK", confidence: 0.91, model: "azure-gpt-4o", reason: "dosage not grounded" },
      ],
    },
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
    // UI-LOGIN-1 / SESSION-MENU-1: LeftRail (mounted via App) reads these for the session-menu
    // affordance — stub them so the rail renders without hitting an undefined export.
    hasStoredToken: vi.fn().mockReturnValue(false),
    logout: vi.fn(),
    signIn: vi.fn(),
    // CONNECT-AI-CONSOLIDATE-1: LeftRail statically imports ProviderSettings (2-section), which
    // imports these — stub so the whole-surface mock covers every export the mounted rail pulls in.
    configProvider: vi.fn().mockResolvedValue({ ok: true, plane: "grading", provider: "openai", last_tested: "" }),
    getProviderStatus: vi.fn().mockResolvedValue({ planes: {} }),
    getModelCatalog: vi.fn().mockResolvedValue({ providers: { openai: [], anthropic: [], azure: { models: [], note: "" } } }),
    bindRole: vi.fn().mockResolvedValue({ ok: true }),
    getRoleBindings: vi.fn().mockResolvedValue({ roles: {}, connected_providers: [] }),
    getCouncilRoster: vi.fn().mockResolvedValue({ panel: [], reviewer_roster: null }),
    setCouncilRoster: vi.fn().mockResolvedValue({ status: "ok" }),
    // the loop under test: stream a run_result (the $0 replay) + the pane directive
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

describe("CHATBIND-2 (A4) — the chat opens + focuses the pane and shows THIS run", () => {
  it("a chat run_result + tool-open_artifact('judges') reaches the focused Judge council tab", async () => {
    render(<App mode="shell" setMode={() => {}} />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "run a $0 replay and show me the judge council" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the directive focused the Reviewers tab AND the lifted run rendered its realized
    // vote there — the Risk reviewer / Flagged are JudgeTab-only (per-reviewer votes), so this
    // proves both the open+focus and the run-data lift end-to-end.
    expect(await screen.findByText("Risk reviewer")).toBeInTheDocument();
    expect(screen.getByText("Flagged")).toBeInTheDocument();
    // the reviewers header pins the focused tab as the Reviewers tab (not the default report)
    expect(screen.getAllByText(/Reviewers/).length).toBeGreaterThan(0);
  });
});
