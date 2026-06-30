/* AuditView.test.jsx — RUNTRAIL-8 A3: the run-provenance report surfaces the lineage
   (grade_path tag + the replay_of baseline) beside the verdict. Mocks bff.js (no live
   BFF), reusing the vi.fn() pattern from RunPanel.test.jsx / artifact.test.jsx. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getAudit: vi.fn().mockResolvedValue({ records: [] }),
  getRunAudit: vi.fn().mockResolvedValue({
    verdict: "BLOCK",
    actor: { id: "ws0_default" },
    grade_path: "replay",
    replay_of: "b1c2d3e4-bbbb-0000-0000-000000000000",
    judges: [{ judge_role: "risk_judge", vote: "BLOCK", reasoning: "WRONG_DOSAGE" }],
  }),
  getRunHistory: vi.fn().mockResolvedValue({
    run_id: "a57bd49d-aaaa",
    history: [
      { run_id: "a57bd49d-aaaa", verdict: "BLOCK", grade_path: "replay", ts: "2026-06-04T00:00:00Z" },
      { run_id: "b1c2d3e4-bbbb", verdict: "PASS", grade_path: "live", ts: "2026-06-03T00:00:00Z" },
    ],
  }),
  rehydrateRun: vi.fn().mockResolvedValue({ verdict: "BLOCK", run_id: "a57bd49d-aaaa" }),
}));

import AuditView from "./AuditView.jsx";
import { getAudit, getRunAudit, getRunHistory, rehydrateRun } from "../bff.js";

beforeEach(() => {
  getAudit.mockClear();
  getRunAudit.mockClear();
  getRunHistory.mockClear();
  rehydrateRun.mockClear();
});

describe("AuditView (tool-audit_log) — RUNTRAIL-8 lineage", () => {
  it("A3 — the run report shows grade_path + replay_of beside the verdict", async () => {
    render(<AuditView runId="a57bd49d-aaaa" />);
    await waitFor(() => expect(getAudit).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Load run/i }));
    await waitFor(() => expect(getRunAudit).toHaveBeenCalledWith("a57bd49d-aaaa"));

    const report = await screen.findByTestId("run-report");
    expect(report).toHaveTextContent("Flagged"); // BLOCK → verdictLabel
    expect(report).toHaveTextContent("Saved replay"); // grade_path: replay → gradeTag
    expect(report).toHaveTextContent("b1c2d3e4"); // replay_of baseline short-id
    expect(report).toHaveTextContent(/replays/i);
  });

  // RUNTRAIL-9 A1: the loaded run report has a History toggle that calls getRunHistory(runId)
  // and lists the prior versions — mirrors RunPanel's per-row History affordance, but inline.
  it("A1 — the run report History toggle calls getRunHistory(runId) and renders versions", async () => {
    render(<AuditView runId="a57bd49d-aaaa" />);
    await waitFor(() => expect(getAudit).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Load run/i }));
    const report = await screen.findByTestId("run-report");

    fireEvent.click(within(report).getByRole("button", { name: /History/i }));
    await waitFor(() => expect(getRunHistory).toHaveBeenCalledWith("a57bd49d-aaaa"));
    const versions = await screen.findAllByTestId("history-version");
    expect(versions).toHaveLength(2);
    expect(versions[1]).toHaveTextContent("b1c2d3e4"); // the prior-version short-id
  });

  // RUNTRAIL-9 A2: the loaded run report has a $0 Rehydrate that calls rehydrateRun(runId)
  // and shows the reconstructed verdict inline.
  it("A2 — the run report Rehydrate $0 calls rehydrateRun(runId) and shows the verdict inline", async () => {
    render(<AuditView runId="a57bd49d-aaaa" />);
    await waitFor(() => expect(getAudit).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Load run/i }));
    const report = await screen.findByTestId("run-report");

    fireEvent.click(within(report).getByRole("button", { name: /Rehydrate/i }));
    await waitFor(() => expect(rehydrateRun).toHaveBeenCalledWith("a57bd49d-aaaa"));
    const rehydrated = await screen.findByTestId("rehydrated-verdict");
    expect(rehydrated).toHaveTextContent("Flagged"); // BLOCK → verdictLabel
  });
});
