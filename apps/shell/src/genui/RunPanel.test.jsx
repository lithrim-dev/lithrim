/* RunPanel.test.jsx — UAP-3 R4: the processing surface loads run-history via GET
   /v1/runs, triggers a graded run via POST /v1/run-eval, and renders the composite
   verdict + the realized council votes. Mocks bff.js (no live BFF). Guards the cost
   gate: a paid mode (in_process) must be confirmed before any call. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getRuns: vi.fn().mockResolvedValue({
    runs: [{ run_id: "a57bd49d-aaaa", verdict: "BLOCK", agent: "ws0_default", ts: "2026-06-04T00:00:00Z" }],
  }),
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
import { getRuns, runEval } from "../bff.js";

beforeEach(() => {
  getRuns.mockClear();
  runEval.mockClear();
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

    // the composite verdict + the realized council votes render
    expect(await screen.findByText("reject")).toBeInTheDocument();
    const votes = await screen.findAllByTestId("council-vote");
    expect(votes).toHaveLength(2);
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

    fireEvent.click(screen.getByRole("button", { name: /Live :8002/i }));
    fireEvent.click(screen.getByRole("button", { name: /Run now/i }));
    fireEvent.click(await screen.findByTestId("cost-confirm"));

    await waitFor(() => expect(runEval).toHaveBeenCalledTimes(1));
    expect(runEval).toHaveBeenCalledWith({ agent: "ws0_default", live: true, in_process: false });
    expect(confirmSpy).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });
});
