/* artifact.reviewershydrate.test.jsx — REVIEWERS-HYDRATE-1: the Reviewers tab must not say
   "No run yet" for a case that HAS a persisted run. Seen live (v0.1.22, ragtruth-queue): the
   Report tab hydrated the stored record (REPORT-HYDRATE-1) while the Reviewers tab, reading
   only the in-session runResult, showed the empty state for the same case. Both tabs now read
   the SAME case record: in-session state wins, else the latest persisted report via
   getCaseReport ($0), else the honest empty state. Written FIRST (RED). */
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
  getRuns: vi.fn(() => Promise.resolve({ runs: [] })),
  getRunReport: vi.fn(),
}));

import { ArtifactPane } from "./artifact.jsx";
import { getCaseReport, getRunAudit } from "./bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

beforeEach(() => {
  getCaseReport.mockReset();
  getRunAudit.mockReset();
  getRunAudit.mockResolvedValue({ withstands: [] });
});

// the shape GET /v1/reports/{case_id} serves for the live ragtruth_10545 record.
const PERSISTED = {
  case_id: "ragtruth_10545",
  grade_path: "in_process",
  pipeline_run_id: "19a98dfe-5ffe-42cd-9d5b-edc5031f9992",
  composite: { verdict: "reject", stage_verdict: "BLOCK", score: 1.0, active_findings: ["SOURCE_CONTRADICTION"], grounded_adjustments: [], floor_adjustments: [] },
  council: {
    case_outcome: "CRITICAL",
    configured: [],
    votes: [
      { judge_role: "risk_judge", vote: "BLOCK", confidence: 0.999, model: "azure/gpt-4.1" },
      { judge_role: "policy_judge", vote: "WARN", confidence: null, model: "azure/Mistral-Large-3" },
      { judge_role: "faithfulness_judge", vote: "BLOCK", confidence: null, model: "azure/Llama-4-Maverick-17B-128E-Instruct-FP8" },
    ],
  },
  calibration_check: { label_status: "unlabeled", status: "unlabeled", verdict_match_rate: null, ece: null, n_cases: 1, n_with_confidence: 1 },
};

const renderJudges = (extra = {}) =>
  render(
    <ArtifactPane {...paneProps} tab="judges" agent="ws0_default" activeCase="ragtruth_10545"
      runStatus="idle" runResult={null} runError={null} {...extra} />,
  );

describe("Reviewers tab — REVIEWERS-HYDRATE-1: a stored run shows its votes", () => {
  it("an armed case with no in-session run hydrates the persisted votes (the same record the Report tab reads)", async () => {
    getCaseReport.mockResolvedValue(PERSISTED);
    renderJudges();
    await screen.findByText(/How each reviewer voted on ragtruth_10545/);
    expect(getCaseReport).toHaveBeenCalledWith("ws0_default", "ragtruth_10545");
    expect(screen.queryByText(/No run yet/)).toBeNull();
    expect(screen.getByText("azure/gpt-4.1")).toBeTruthy();
    expect(screen.getByText(/2 blocking vote\(s\)/)).toBeTruthy();
  });

  it("no persisted run (404) keeps the honest empty state", async () => {
    getCaseReport.mockRejectedValue(new Error("404"));
    renderJudges();
    await waitFor(() => expect(getCaseReport).toHaveBeenCalled());
    expect(await screen.findByText(/No run yet/)).toBeTruthy();
  });

  it("no armed case → nothing fetched, empty state as today", () => {
    renderJudges({ activeCase: null });
    expect(getCaseReport).not.toHaveBeenCalled();
    expect(screen.getByText(/No run yet/)).toBeTruthy();
  });

  it("an in-session run wins over the stored record", async () => {
    getCaseReport.mockResolvedValue(PERSISTED);
    renderJudges({
      runStatus: "ready",
      runResult: { ...PERSISTED, case_id: "in_session_case", council: { ...PERSISTED.council, votes: [PERSISTED.council.votes[0]] } },
    });
    expect(await screen.findByText(/How each reviewer voted on in_session_case/)).toBeTruthy();
    expect(getCaseReport).not.toHaveBeenCalled();
  });
});
