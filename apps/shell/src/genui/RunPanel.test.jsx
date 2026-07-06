/* RunPanel.test.jsx — UAP-3 R4: the processing surface loads run-history via GET
   /v1/runs, triggers a graded run via POST /v1/run-eval, and renders the composite
   verdict + the realized council votes. Mocks bff.js (no live BFF). Guards the cost
   gate: a paid mode (in_process) must be confirmed before any call. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getRuns: vi.fn().mockResolvedValue({
    runs: [{
      run_id: "a57bd49d-aaaa", verdict: "BLOCK", agent: "ws0_default", ts: "2026-06-04T00:00:00Z",
      grade_path: "replay", replay_of: "b1c2d3e4-bbbb-0000-0000-000000000000",
    }],
  }),
  getRunHistory: vi.fn().mockResolvedValue({
    run_id: "a57bd49d-aaaa",
    history: [
      { run_id: "a57bd49d-aaaa", verdict: "BLOCK", grade_path: "replay", ts: "2026-06-04T00:00:00Z" },
      { run_id: "b1c2d3e4-bbbb", verdict: "PASS", grade_path: "live", ts: "2026-06-03T00:00:00Z" },
    ],
  }),
  rehydrateRun: vi.fn().mockResolvedValue({ verdict: "BLOCK", run_id: "a57bd49d-aaaa" }),
  runEval: vi.fn().mockResolvedValue({
    pipeline_run_id: "a57bd49d-94cd-4397-8c53-f8cbaad3aec2",
    grade_path: "replay",
    composite: { verdict: "reject", stage_verdict: "BLOCK", score: 1.0 },
    council: {
      votes: [
        { judge_role: "risk_judge", vote: "BLOCK", confidence: 0.99, model: "gpt-4.1", findings: ["WRONG_DOSAGE"] },
        { judge_role: "policy_judge", vote: "PASS", confidence: null, model: "mistral", findings: [] },
      ],
    },
  }),
}));

import RunPanel from "./RunPanel.jsx";
import { getRuns, runEval, getRunHistory, rehydrateRun } from "../bff.js";

beforeEach(() => {
  getRuns.mockClear();
  runEval.mockClear();
  getRunHistory.mockClear();
  rehydrateRun.mockClear();
});

describe("RunPanel (tool-run_panel)", () => {
  it("loads run-history on mount and triggers a $0 replay run (no confirm)", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<RunPanel />);

    // history loads via GET /v1/runs
    await waitFor(() => expect(getRuns).toHaveBeenCalled());
    expect(await screen.findByText(/Run history \(1\)/)).toBeInTheDocument();

    // replay is the default mode → Run now fires WITHOUT a cost confirm
    fireEvent.click(screen.getByRole("button", { name: /Run now/i }));
    await waitFor(() => expect(runEval).toHaveBeenCalledTimes(1));
    expect(runEval).toHaveBeenCalledWith({ agent: "ws0_default", live: false, in_process: false });
    expect(confirmSpy).not.toHaveBeenCalled();

    // the composite result + the realized reviewer votes render (verdict relabeled via copy.js)
    expect(await screen.findByText("Result")).toBeInTheDocument();
    const votes = await screen.findAllByTestId("council-vote");
    expect(votes).toHaveLength(2);
    expect(screen.getAllByText("Flagged").length).toBeGreaterThan(0); // reject/BLOCK → plain outcome
    expect(screen.getByText("Risk reviewer")).toBeInTheDocument(); // risk_judge → roleLabel
    expect(screen.getByText("WRONG_DOSAGE", { exact: false })).toBeInTheDocument();
    // history refreshed after the run (mount + post-run)
    expect(getRuns.mock.calls.length).toBeGreaterThanOrEqual(2);
    confirmSpy.mockRestore();
  });

  // EVAL-FLOW A3 / W2a (S-BS-69): the paid gate is the in-DOM CostModal, NOT window.confirm.
  // A native confirm() freezes the renderer to CDP (memory browser-mcp-confirm-blocks-renderer),
  // so a paid "Run now" must be CDP-driveable. These tests REPLACE the prior window.confirm
  // assertions (which were correct for the old code, now wrong for the in-DOM gate — EXECUTOR.md §4).
  it("test_paid_run_uses_indom_costmodal — confirm fires the run once; cancel makes no call; no window.confirm", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<RunPanel />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());

    // switch to the paid in-process mode, then attempt to run → the in-DOM modal opens (NO call yet).
    fireEvent.click(screen.getByRole("button", { name: /In-process trio/i }));
    fireEvent.click(screen.getByRole("button", { name: /Run now/i }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(runEval).not.toHaveBeenCalled(); // opening the modal makes NO call

    // CANCEL aborts with no /v1/run-eval call.
    fireEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(runEval).not.toHaveBeenCalled();

    // re-open and CONFIRM → the run fires exactly once, in-process.
    fireEvent.click(screen.getByRole("button", { name: /Run now/i }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("cost-confirm"));
    await waitFor(() => expect(runEval).toHaveBeenCalledTimes(1));
    expect(runEval).toHaveBeenCalledWith({ agent: "ws0_default", live: false, in_process: true });

    // window.confirm is NEVER called — the gate is fully in-DOM.
    expect(confirmSpy).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("the live mode also routes through the in-DOM modal (paid, CDP-driveable)", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<RunPanel />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Live run/i }));
    fireEvent.click(screen.getByRole("button", { name: /Run now/i }));
    fireEvent.click(await screen.findByTestId("cost-confirm"));

    await waitFor(() => expect(runEval).toHaveBeenCalledTimes(1));
    expect(runEval).toHaveBeenCalledWith({ agent: "ws0_default", live: true, in_process: false });
    expect(confirmSpy).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  // RUNTRAIL-8 A1: a history row surfaces the lineage (grade_path tag + the replay_of baseline).
  it("A1 — a history row shows grade_path + replay_of when present", async () => {
    render(<RunPanel />);
    const row = await screen.findByTestId("history-row");
    expect(row).toHaveTextContent("Saved replay"); // grade_path: replay → gradeTag label
    expect(row).toHaveTextContent("b1c2d3e4"); // replay_of baseline short-id
    expect(row).toHaveTextContent(/replays/i); // the "↩ replays {id8}" affordance
  });

  // RUNTRAIL-8 A2: the per-row History toggle calls getRunHistory(run_id) and lists the versions.
  it("A2 — the History toggle calls getRunHistory(run_id) and renders prior versions", async () => {
    render(<RunPanel />);
    const row = await screen.findByTestId("history-row");
    fireEvent.click(within(row).getByRole("button", { name: /History/i }));
    await waitFor(() => expect(getRunHistory).toHaveBeenCalledWith("a57bd49d-aaaa"));
    const versions = await screen.findAllByTestId("history-version");
    expect(versions).toHaveLength(2);
    expect(versions[1]).toHaveTextContent("b1c2d3e4"); // the prior-version short-id
  });

  // RUNTRAIL-8 A2: the Rehydrate button calls rehydrateRun(run_id) and shows the reconstructed verdict.
  it("A2 — the Rehydrate button calls rehydrateRun(run_id) and shows the verdict inline", async () => {
    render(<RunPanel />);
    const row = await screen.findByTestId("history-row");
    fireEvent.click(within(row).getByRole("button", { name: /Rehydrate/i }));
    await waitFor(() => expect(rehydrateRun).toHaveBeenCalledWith("a57bd49d-aaaa"));
    const rehydrated = await screen.findByTestId("rehydrated-verdict");
    expect(rehydrated).toHaveTextContent("Flagged"); // BLOCK → verdictLabel
  });

  // Theme B (B2/B3): a failed run shows a CALM, leak-free reason (friendlyError) + a Try again
  // that re-fires the run — never a raw HTTP/path/stack, never a dead end.
  it("a failed run shows a friendly reason + a Try again that re-runs", async () => {
    runEval.mockRejectedValueOnce(new Error("POST /v1/run-eval → 500: traceback ..."));
    render(<RunPanel />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Run now/i }));
    // the calm reason renders (the raw HTTP envelope/stack is NOT shown)
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/something went wrong on the server/i);
    expect(alert).not.toHaveTextContent(/traceback|run-eval|500/);

    // Try again re-fires the run; the next call succeeds and the result renders
    fireEvent.click(within(alert).getByRole("button", { name: /Try again/i }));
    expect(await screen.findByText("Result")).toBeInTheDocument();
  });

  // SWEEP (RIGOR-1 / Q1 — NEW-G3): the "Reliability sweep" control is a $0 read that dispatches
  // the lithrim:show-sweep window bridge (the CenterPane renders the tool-sweep_card inline).
  // It never spends and never calls runEval — it only emits the bridge event.
  it("the 'Reliability sweep' control dispatches lithrim:show-sweep (a $0 read, no run)", async () => {
    const heard = vi.fn();
    window.addEventListener("lithrim:show-sweep", heard);
    render(<RunPanel />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("sweep-trigger"));
    expect(heard).toHaveBeenCalledTimes(1);
    expect(runEval).not.toHaveBeenCalled(); // $0 — the sweep read spends nothing
    window.removeEventListener("lithrim:show-sweep", heard);
  });
});
