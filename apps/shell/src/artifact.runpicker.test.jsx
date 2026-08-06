/* artifact.runpicker.test.jsx — RUN-SCOPED-REPORT-1: the Report pane can open a PAST run.

   THE GAP: the report store keeps ONE record per case (every grade upserts it), so the pane
   could only ever show the newest grade — clicking an older row silently showed the latest.
   THE FIX: ReportTab lists this case's runs (GET /v1/runs?case_id=) and renders the picked
   one via getRunReport (GET /v1/runs/{id}/report, a $0 blob read in the same record shape).

   Why it matters: two runs of ONE case under a frozen config disagreeing is the evidence an
   LLM judge is not deterministic — the argument for a deterministic floor and for escalating
   to a human exactly where runs disagree. Component-level (the full-App mount bypasses
   vi.mock via its dynamic import — the known quirk). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./bff.js", () => ({
  getOntology: vi.fn(),
  getCorpus: vi.fn(),
  getCase: vi.fn(),
  listCaseBrowser: vi.fn(),
  recordMetaVerdict: vi.fn(),
  getRunAudit: vi.fn(),
  getCaseReport: vi.fn(),
  getRuns: vi.fn(),
  getRunReport: vi.fn(),
}));

import { ArtifactPane } from "./artifact.jsx";
import { getCaseReport, getRunAudit, getRuns, getRunReport } from "./bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };
const CASE = "cv01_hiv";

const record = (verdict, stage, findings, runId) => ({
  case_id: CASE,
  grade_path: "in_process",
  pipeline_run_id: runId,
  composite: {
    verdict, stage_verdict: stage, score: 0.5, active_findings: findings,
    grounded_adjustments: [], floor_adjustments: [], floor_block_count: 0,
  },
  council: { votes: [{ judge_role: "openbio_judge", vote: stage, confidence: 0.9 }], configured: [] },
});

// the exhibit: same case, same frozen config, the raised code CHANGES between runs
const LATEST = record("reject", "BLOCK", ["INTERNAL_INCONSISTENCY"], "run-newer");
const EARLIER = record("reject", "BLOCK", ["UPCODED_DIAGNOSIS"], "run-older");
const RUNS = {
  runs: [
    { run_id: "run-newer", ts: "2026-08-06T16:43:10Z", verdict: "WARN", grounded_verdict: "BLOCK", grade_path: "in_process" },
    { run_id: "run-older", ts: "2026-08-06T16:41:03Z", verdict: "WARN", grounded_verdict: "BLOCK", grade_path: "in_process" },
  ],
};

beforeEach(() => {
  [getCaseReport, getRunAudit, getRuns, getRunReport].forEach((m) => m.mockReset());
  getRunAudit.mockResolvedValue({ withstands: [] });
  getCaseReport.mockResolvedValue(LATEST);
  getRuns.mockResolvedValue(RUNS);
  getRunReport.mockResolvedValue(EARLIER);
});

const mount = () =>
  render(
    <ArtifactPane {...paneProps} tab="report" agent="ws0_default" activeCase={CASE}
      runStatus="idle" runResult={null} runError={null} />,
  );

describe("ReportTab — RUN-SCOPED-REPORT-1: a past run is openable", () => {
  it("lists this case's runs, scoped to the armed case and active agent", async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId("run-picker")).toBeInTheDocument());
    expect(getRuns).toHaveBeenCalledWith(50, { agent: "ws0_default", caseId: CASE });
    // the newest grade still renders by default — the picker is additive, not a mode switch
    expect(screen.getByText("Internal inconsistency")).toBeInTheDocument();
  });

  it("picking an earlier run renders THAT run's result, not the latest", async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId("run-picker")).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText("run run-older"));

    await waitFor(() => expect(getRunReport).toHaveBeenCalledWith("run-older"));
    // the earlier run's finding replaces the latest one — the whole point
    await waitFor(() => expect(screen.getByText("Upcoded diagnosis")).toBeInTheDocument());
    expect(screen.queryByText("Internal inconsistency")).toBeNull();
  });

  it("Latest returns to the newest grade without re-fetching a run", async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId("run-picker")).toBeInTheDocument());
    await userEvent.click(screen.getByLabelText("run run-older"));
    await waitFor(() => expect(screen.getByText("Upcoded diagnosis")).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText("latest run"));

    await waitFor(() => expect(screen.getByText("Internal inconsistency")).toBeInTheDocument());
  });

  it("a single-run case shows NO picker (nothing to compare)", async () => {
    getRuns.mockResolvedValue({ runs: [RUNS.runs[0]] });
    mount();
    await waitFor(() => expect(screen.getByText("Internal inconsistency")).toBeInTheDocument());
    expect(screen.queryByTestId("run-picker")).toBeNull();
  });

  it("an unreadable run history degrades silently — the latest report still renders", async () => {
    getRuns.mockRejectedValue(new Error("GET /v1/runs → 500"));
    mount();
    await waitFor(() => expect(screen.getByText("Internal inconsistency")).toBeInTheDocument());
    expect(screen.queryByTestId("run-picker")).toBeNull();
  });
});
