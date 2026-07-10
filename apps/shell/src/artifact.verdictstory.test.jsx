/* artifact.verdictstory.test.jsx — FLOOR-STORY-1: the Report banner tells ONE story on a
   floor-cleared run (live 9d89cfab, cv_mts_002): pre-floor the council flagged it, the
   grounding floor cleared every finding, final verdict Passed. The banner must never title
   "Flagged" over a "Passed" grade; the flip renders as the product's story. Runs with NO
   grounded data render exactly as today (pinned). The fact-check section heading claims
   "changed the result" ONLY when a floor_block row exists. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

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
import { getRunAudit } from "./bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

beforeEach(() => {
  getRunAudit.mockReset();
  getRunAudit.mockResolvedValue({ withstands: [] });
});

// The live repro shape (run 9d89cfab): all 5 votes BLOCK (pre-floor), the grounding floor
// suppressed all 3 findings, post-floor verdict PASS. council.case_outcome carries the
// PRE-FIX server's contradicting "FLAGGED" on purpose — the banner must stay coherent.
const FLOOR_CLEARED_RUN = {
  case_id: "cv_mts_002_clean_subsumption_alzheimers",
  grade_path: "in_process",
  pipeline_run_id: "9d89cfab",
  composite: {
    verdict: "approve",
    stage_verdict: "PASS",
    score: 0.0,
    active_findings: [],
    grounded_adjustments: [
      { flag: "FABRICATED_CLAIM", action: "suppress", contract: "repro/2", reason: "is-a subsumption" },
      { flag: "FABRICATED_CLAIM", action: "suppress", contract: "repro/2", reason: "is-a subsumption" },
      { flag: "FABRICATED_HISTORY", action: "suppress", contract: "record-presence/v1", reason: "present in the record" },
    ],
    floor_adjustments: [],
  },
  grounded: { verdict: "PASS", original_verdict: "BLOCK", suppressed: [{}, {}, {}] },
  council: {
    case_outcome: "FLAGGED",
    votes: [
      { judge_role: "risk_judge", vote: "BLOCK", confidence: 0.9 },
      { judge_role: "policy_judge", vote: "BLOCK", confidence: 0.9 },
      { judge_role: "faithfulness_judge", vote: "BLOCK", confidence: 0.9 },
      { judge_role: "reviewer_d", vote: "BLOCK", confidence: 0.9 },
      { judge_role: "reviewer_e", vote: "BLOCK", confidence: 0.9 },
    ],
  },
  calibration_check: { label_status: "unlabeled", status: "unlabeled", verdict_match_rate: null, ece: null, n_cases: 1, n_with_confidence: 0 },
};

// A genuinely-flagged run with NO grounded data — the banner must render exactly as today.
const FLAGGED_RUN_NO_FLOOR = {
  case_id: "clinverdict_case06",
  grade_path: "in_process",
  pipeline_run_id: "run-c6",
  composite: {
    verdict: "reject",
    stage_verdict: "BLOCK",
    score: 1.0,
    active_findings: ["INTENT_ERASURE"],
    grounded_adjustments: [],
    floor_adjustments: [],
  },
  council: {
    case_outcome: "FLAGGED",
    votes: [
      { judge_role: "faithfulness_judge", vote: "BLOCK", confidence: 0.9, reason: "reject" },
      { judge_role: "risk_judge", vote: "PASS", confidence: 1.0 },
    ],
  },
  calibration_check: { label_status: "unlabeled", status: "unlabeled", verdict_match_rate: null, ece: null, n_cases: 1, n_with_confidence: 0 },
};

describe("Report banner — FLOOR-STORY-1: a floor-cleared run tells one coherent story", () => {
  it("never titles the chip 'Flagged' above a 'Passed' grade", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={FLOOR_CLEARED_RUN} runError={null} />,
    );
    const title = container.querySelector(".rb-t").textContent;
    const grade = container.querySelector(".rb-grade").textContent;
    expect(grade).toBe("Passed");
    expect(title).not.toMatch(/flagged/i);
  });

  it("renders the flip story: reviewers flagged it, the floor cleared N false alarms, final Passed", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={FLOOR_CLEARED_RUN} runError={null} />,
    );
    const banner = container.querySelector(".report-banner").textContent;
    expect(banner).toMatch(/Reviewers flagged it · a fact-check cleared 3 false alarms · final: Passed/);
  });

  it("a run with NO grounded data renders exactly as today (Flagged chip + Flagged grade)", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={FLAGGED_RUN_NO_FLOOR} runError={null} />,
    );
    expect(container.querySelector(".rb-t").textContent).toBe("Flagged");
    expect(container.querySelector(".rb-grade").textContent).toBe("Flagged");
    expect(container.querySelector(".report-banner").textContent).not.toMatch(/fact-check cleared/);
  });
});

describe("ReportSummary — FLOOR-STORY-1: the floor clear is said explicitly, never a contradiction", () => {
  it("floor-cleared: says reviewers flagged it AND the fact-check layer cleared it, final passed", () => {
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={FLOOR_CLEARED_RUN} runError={null} />);
    const text = screen.getByTestId("report-summary").textContent;
    expect(text).toMatch(/This case passed\./);
    expect(text).toMatch(/flagged it/i);
    expect(text).toMatch(/fact-check layer cleared/i);
    expect(text).toMatch(/Final: passed\./);
    // the contradiction pair must never co-occur
    expect(text).not.toMatch(/No reviewer raised an issue/);
  });

  it("never emits 'flagged it' and 'No reviewer raised an issue' together (PASS + flagged votes, no clears)", () => {
    const weird = {
      ...FLOOR_CLEARED_RUN,
      composite: { ...FLOOR_CLEARED_RUN.composite, grounded_adjustments: [] },
      grounded: undefined,
    };
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={weird} runError={null} />);
    const text = screen.getByTestId("report-summary").textContent;
    if (/flagged it/i.test(text)) expect(text).not.toMatch(/No reviewer raised an issue/);
  });

  it("a clean PASS still reads 'No reviewer raised an issue.' (pinned)", () => {
    const clean = {
      ...FLAGGED_RUN_NO_FLOOR,
      composite: { ...FLAGGED_RUN_NO_FLOOR.composite, verdict: "approve", stage_verdict: "PASS", score: 0, active_findings: [] },
      council: { case_outcome: "CLEAR", votes: [{ judge_role: "risk_judge", vote: "PASS", confidence: 1.0 }] },
    };
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={clean} runError={null} />);
    const text = screen.getByTestId("report-summary").textContent;
    expect(text).toMatch(/No reviewer raised an issue\./);
    expect(text).not.toMatch(/flagged it/i);
  });
});

describe("Fact-check section heading — honest about whether the result changed", () => {
  const floorRun = (adjustments) => ({
    ...FLAGGED_RUN_NO_FLOOR,
    composite: { ...FLAGGED_RUN_NO_FLOOR.composite, floor_adjustments: adjustments },
  });

  it("all-inconclusive rows: the heading does NOT claim the result changed", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runError={null}
        runResult={floorRun([
          { flag: "WRONG_DOSAGE", action: "floor_inconclusive", contract_type: "dose-range", contract: "v1", conforms: null, disposition: "tool unreachable" },
        ])} />,
    );
    expect(container.textContent).not.toMatch(/a fact-check changed the result/);
    expect(container.textContent).toMatch(/fact-checks ran \(inconclusive\)/);
  });

  it("a floor_block row keeps the 'changed the result' heading (pinned)", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runError={null}
        runResult={floorRun([
          { flag: "SILENT_DEGRADATION", action: "floor_block", contract_type: "silent_degradation", contract: "v1", conforms: false, disposition: "inject_block" },
          { flag: "WRONG_DOSAGE", action: "floor_inconclusive", contract_type: "dose-range", contract: "v1", conforms: null, disposition: "tool unreachable" },
        ])} />,
    );
    expect(container.textContent).toMatch(/a fact-check changed the result/);
  });
});
