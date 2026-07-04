/* artifact.reporthydrate.test.jsx — REPORT-HYDRATE-1: an ARMED case with persisted runs must
   not read "No evaluation yet". When the pane has no in-session run (runStatus idle,
   runResult null) and a case is armed, ReportTab hydrates the LATEST persisted report for
   that case via getCaseReport (GET /v1/reports/{case_id}, a $0 read) and renders it with the
   EXACT same renderer the in-session run feeds — honestly labeled by its stored grade_path.
   No armed case, an in-session run, or a 404 → behavior unchanged. Component-level on purpose
   (the full-App mount bypasses vi.mock via its dynamic import — the known quirk). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("./bff.js", () => ({
  getOntology: vi.fn(),
  getCorpus: vi.fn(),
  getCase: vi.fn(),
  listCaseBrowser: vi.fn(),
  recordMetaVerdict: vi.fn(),
  getRunAudit: vi.fn(),
  getCaseReport: vi.fn(),
}));

import { ArtifactPane } from "./artifact.jsx";
import { getCaseReport, getRunAudit } from "./bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

beforeEach(() => {
  getCaseReport.mockReset();
  getRunAudit.mockReset();
  getRunAudit.mockResolvedValue({ withstands: [] });
});

// the shape GET /v1/reports/{case_id} serves — the run-eval record contract (composite +
// calibration_check + council + grade_path), for the live repro case.
const PERSISTED_REPORT = {
  case_id: "cv_mts_002_clean_subsumption_alzheimers",
  grade_path: "replay",
  pipeline_run_id: "run-hydrate-0001",
  composite: {
    verdict: "reject",
    stage_verdict: "BLOCK",
    score: 0.9,
    active_findings: ["FABRICATED_CLAIM"],
    grounded_adjustments: [],
    floor_adjustments: [],
    floor_block_count: 0,
  },
  calibration_check: { label_status: "unlabeled", status: "unlabeled", verdict_match_rate: null, ece: null, n_cases: 1, n_with_confidence: 1 },
  council: { votes: [{ judge_role: "faithfulness_judge", vote: "BLOCK", confidence: 0.9 }], configured: [] },
};

const IN_SESSION_RUN = {
  case_id: "some_other_case",
  grade_path: "in_process",
  composite: {
    verdict: "approve",
    stage_verdict: "PASS",
    score: 0.0,
    active_findings: [],
    grounded_adjustments: [],
    floor_adjustments: [],
    floor_block_count: 0,
  },
  calibration_check: { label_status: "unlabeled", status: "unlabeled", verdict_match_rate: null, ece: null, n_cases: 1, n_with_confidence: 0 },
};

describe("ReportTab — REPORT-HYDRATE-1: armed case hydrates the latest persisted run", () => {
  it("an armed case with no in-session run fetches + renders the persisted report (the exact renderer)", async () => {
    getCaseReport.mockResolvedValue(PERSISTED_REPORT);
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" agent="repro_agent"
        activeCase="cv_mts_002_clean_subsumption_alzheimers"
        runStatus="idle" runResult={null} runError={null} />,
    );
    await waitFor(() => expect(screen.queryByText(/No evaluation yet/i)).toBeNull());
    // the persisted verdict renders through the SAME renderer (banner + finding + summary)
    expect(screen.getByText("Fabricated claim")).toBeInTheDocument(); // flagLabel(FABRICATED_CLAIM)
    expect(container.textContent).toContain("cv_mts_002_clean_subsumption_alzheimers");
    // honest cost/path label: a stored replay reads as the saved replay, never a paid claim
    expect(container.textContent).toContain("Saved replay · free");
    // the fetch targeted the ARMED case for the ACTIVE agent
    expect(getCaseReport).toHaveBeenCalledWith("repro_agent", "cv_mts_002_clean_subsumption_alzheimers");
  });

  it("no armed case → the empty state is unchanged and NO fetch fires", () => {
    render(
      <ArtifactPane {...paneProps} tab="report" agent="repro_agent" activeCase={null}
        runStatus="idle" runResult={null} runError={null} />,
    );
    expect(screen.getByText(/No evaluation yet/i)).toBeInTheDocument();
    expect(getCaseReport).not.toHaveBeenCalled();
  });

  it("an armed case with NO persisted report (404) keeps the empty state — no crash, no fake report", async () => {
    getCaseReport.mockRejectedValue(new Error("GET /v1/reports/x → 404"));
    render(
      <ArtifactPane {...paneProps} tab="report" agent="repro_agent" activeCase="never_graded"
        runStatus="idle" runResult={null} runError={null} />,
    );
    await waitFor(() => expect(getCaseReport).toHaveBeenCalled());
    expect(screen.getByText(/No evaluation yet/i)).toBeInTheDocument();
  });

  it("an in-session run takes precedence — no hydration fetch, the fresh result renders", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" agent="repro_agent"
        activeCase="cv_mts_002_clean_subsumption_alzheimers"
        runStatus="ready" runResult={IN_SESSION_RUN} runError={null} />,
    );
    expect(getCaseReport).not.toHaveBeenCalled();
    expect(container.textContent).toContain("some_other_case");
  });

  it("a run in flight (loading) shows the running state, not a stale hydrated report", () => {
    render(
      <ArtifactPane {...paneProps} tab="report" agent="repro_agent"
        activeCase="cv_mts_002_clean_subsumption_alzheimers"
        runStatus="loading" runResult={null} runError={null} />,
    );
    expect(screen.getByText(/Running the evaluation/i)).toBeInTheDocument();
    expect(getCaseReport).not.toHaveBeenCalled();
  });
});
