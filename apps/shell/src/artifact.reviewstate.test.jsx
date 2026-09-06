/* artifact.reviewstate.test.jsx — REVIEW-STATE-UI-1: the report pane carries the reviewer's
   three-state decision the engine now computes (composite.review): FLAGGED only when a
   deterministic check contradicted the artifact, CLEARED only when a check confirmed it or
   disproved the judges' signal, everything else NEEDS A PERSON with the reason. A record with
   no review block (a pre-cycle server) renders exactly as today. The fact-check rows print the
   evidence the check produced, the heading claims "changed the result" only when the pre-floor
   verdict differs from the final one, and the passes a check recorded render as confirmations
   so an escalated case shows what WAS verified. Written FIRST (RED). */
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
  getRuns: vi.fn(() => Promise.resolve({ runs: [] })),
  getRunReport: vi.fn(),
}));

import { ArtifactPane } from "./artifact.jsx";
import { getRunAudit } from "./bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

beforeEach(() => {
  getRunAudit.mockReset();
  getRunAudit.mockResolvedValue({ withstands: [] });
});

const CAL = { label_status: "unlabeled", status: "unlabeled", verdict_match_rate: null, ece: null, n_cases: 1, n_with_confidence: 1 };
const BLOCK_VOTES = [
  { judge_role: "risk_judge", vote: "BLOCK", confidence: 0.9 },
  { judge_role: "policy_judge", vote: "WARN", confidence: null },
  { judge_role: "faithfulness_judge", vote: "BLOCK", confidence: null },
];
const PASS_VOTES = [
  { judge_role: "risk_judge", vote: "PASS", confidence: 0.9 },
  { judge_role: "policy_judge", vote: "PASS", confidence: null },
  { judge_role: "faithfulness_judge", vote: "PASS", confidence: null },
];

const VALUE_BLOCK_ROW = {
  flag: "SOURCE_CONTRADICTION", action: "floor_block", contract_type: "value_grounding",
  contract: "value-grounding/1", conforms: false, disposition: "VIOLATION",
  evidence: { checked: 1, missing: ["50"], present: [], reason: "values stated in the artifact are absent from the record", source_kind: "record" },
};
const VALUE_PASS_ROW = {
  flag: "SOURCE_CONTRADICTION", action: "floor_pass", contract_type: "value_grounding",
  contract: "value-grounding/1", conforms: true, disposition: "CONFORMS",
  evidence: { checked: 4, present: ["7:30", "5:00", "1150", "4.5"], missing: [], reason: "every value the artifact states is present in the source", source_kind: "record" },
};

// the live ragtruth_10545 shape (v0.1.22 stack): council BLOCK, the floor enforced on its own
// evidence — the check CONFIRMED the reviewers, it did not flip them.
const FLAGGED = {
  case_id: "ragtruth_10545", grade_path: "in_process", pipeline_run_id: "run-rs-flagged",
  composite: {
    verdict: "reject", stage_verdict: "BLOCK", score: 1.0,
    active_findings: ["UNSUPPORTED_ASSERTION", "SOURCE_CONTRADICTION"],
    grounded_adjustments: [], floor_adjustments: [VALUE_BLOCK_ROW], floor_passes: [], floor_pass_count: 0,
    coverage: { grounded: 1, cleared: 0, floor_passes: 0, floor_backstopped: true },
    review: {
      state: "FLAGGED", check: "value_grounding",
      evidence: "value_grounding: values stated in the artifact are absent from the record; missing ['50']",
      reason: "a deterministic check contradicted the artifact",
      judge_codes: ["UNSUPPORTED_ASSERTION"], floor_backstopped: true, verdict: "BLOCK", verdict_no_floor: "BLOCK",
    },
  },
  grounded: { verdict: "BLOCK", original_verdict: "BLOCK", verdict_no_floor: "BLOCK", suppressed: [], floor_blocks: [{ flag: "SOURCE_CONTRADICTION", injected: true }] },
  council: { case_outcome: "CRITICAL", votes: BLOCK_VOTES, configured: [] },
  calibration_check: CAL,
};

// the same check, but the reviewers had PASSED: the floor flipped the verdict.
const FLIPPED = {
  ...FLAGGED, case_id: "ragtruth_flip", pipeline_run_id: "run-rs-flip",
  composite: { ...FLAGGED.composite, review: { ...FLAGGED.composite.review, verdict_no_floor: "PASS" } },
  grounded: { ...FLAGGED.grounded, original_verdict: "PASS", verdict_no_floor: "PASS" },
  council: { case_outcome: "CLEAR", votes: PASS_VOTES, configured: [] },
};

// the live ragtruth_9001 shape: human-clean record, council BLOCK on three signals, the value
// check found every number present — nothing contradicted, nothing proven: a person decides.
const ESCALATED = {
  case_id: "ragtruth_9001", grade_path: "in_process", pipeline_run_id: "run-rs-esc",
  composite: {
    verdict: "reject", stage_verdict: "BLOCK", score: 1.0,
    active_findings: ["UNSUPPORTED_ASSERTION", "SOURCE_CONTRADICTION", "MISSING_CONTEXT"],
    grounded_adjustments: [], floor_adjustments: [], floor_passes: [VALUE_PASS_ROW], floor_pass_count: 1,
    coverage: { grounded: 0, cleared: 0, floor_passes: 1, floor_backstopped: false },
    review: {
      state: "ESCALATED", check: null,
      evidence: "value_grounding confirmed 4 value(s) present",
      reason: "judges raised ['UNSUPPORTED_ASSERTION', 'SOURCE_CONTRADICTION', 'MISSING_CONTEXT']; no check could confirm or refute it",
      judge_codes: ["MISSING_CONTEXT", "SOURCE_CONTRADICTION", "UNSUPPORTED_ASSERTION"],
      floor_backstopped: false, verdict: "BLOCK", verdict_no_floor: "BLOCK",
    },
  },
  grounded: { verdict: "BLOCK", original_verdict: "BLOCK", verdict_no_floor: "BLOCK", suppressed: [], floor_blocks: [] },
  council: { case_outcome: "CRITICAL", votes: BLOCK_VOTES, configured: [] },
  calibration_check: CAL,
};

const CLEARED = {
  case_id: "ragtruth_clean", grade_path: "in_process", pipeline_run_id: "run-rs-clear",
  composite: {
    verdict: "approve", stage_verdict: "PASS", score: 0.0,
    active_findings: [], grounded_adjustments: [], floor_adjustments: [],
    floor_passes: [{ ...VALUE_PASS_ROW, evidence: { ...VALUE_PASS_ROW.evidence, checked: 2, present: ["4", "312"] } }], floor_pass_count: 1,
    coverage: { grounded: 0, cleared: 0, floor_passes: 1, floor_backstopped: true },
    review: {
      state: "CLEARED", check: "value_grounding",
      evidence: "value_grounding: 2 value(s) checked, all present in the source",
      reason: "a deterministic check confirmed the artifact",
      judge_codes: [], floor_backstopped: true, verdict: "PASS", verdict_no_floor: "PASS",
    },
  },
  grounded: { verdict: "PASS", original_verdict: "PASS", verdict_no_floor: "PASS", suppressed: [], floor_blocks: [] },
  council: { case_outcome: "CLEAR", votes: PASS_VOTES, configured: [] },
  calibration_check: CAL,
};

// a pre-cycle record: no review block → today's rendering, byte for byte in spirit.
const LEGACY = {
  ...ESCALATED, case_id: "legacy_case", pipeline_run_id: "run-legacy",
  composite: { verdict: "reject", stage_verdict: "BLOCK", score: 1.0, active_findings: ["UNSUPPORTED_ASSERTION"], grounded_adjustments: [], floor_adjustments: [] },
  grounded: undefined,
};

const renderReport = (runResult) =>
  render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runError={null} runResult={runResult} />);

describe("Report banner — the three reviewer states", () => {
  it("FLAGGED: titles the banner Flagged and says a check contradicted the artifact", () => {
    const { container } = renderReport(FLAGGED);
    expect(container.querySelector(".rb-t").textContent).toBe("Flagged");
    expect(screen.getByTestId("review-reason").textContent).toMatch(/a deterministic check contradicted the artifact/);
    expect(screen.getByTestId("review-reason").textContent).toMatch(/value_grounding/);
  });

  it("ESCALATED: titles the banner Needs a person with the reason, never Critical", () => {
    const { container } = renderReport(ESCALATED);
    expect(container.querySelector(".rb-t").textContent).toBe("Needs a person");
    expect(container.textContent).not.toMatch(/Critical/);
    expect(screen.getByTestId("review-reason").textContent).toMatch(/no check could confirm or refute it/);
  });

  it("CLEARED: titles the banner Cleared and names the check that confirmed it", () => {
    const { container } = renderReport(CLEARED);
    expect(container.querySelector(".rb-t").textContent).toBe("Cleared");
    expect(screen.getByTestId("review-reason").textContent).toMatch(/2 value\(s\) checked, all present in the source/);
  });

  it("a record with no review block renders exactly as today (outcome label, no reason line)", () => {
    const { container } = renderReport(LEGACY);
    expect(container.querySelector(".rb-t").textContent).toBe("Critical");
    expect(screen.queryByTestId("review-reason")).toBeNull();
  });
});

describe("Fact-check rows — the evidence, and an honest heading", () => {
  it("a blocked row prints what the check found: the reason and the missing value", () => {
    const { container } = renderReport(FLAGGED);
    const row = screen.getByTestId("floor-row-evidence");
    expect(row.textContent).toMatch(/absent from the record/);
    expect(row.textContent).toMatch(/missing:\s*50/);
    expect(container.textContent).toMatch(/Blocked by a fact-check · value_grounding/);
  });

  it("the check CONFIRMED the reviewers (pre-floor BLOCK, final BLOCK): the heading says confirmed, not changed", () => {
    const { container } = renderReport(FLAGGED);
    expect(container.textContent).toMatch(/a fact-check confirmed the result/);
    expect(container.textContent).not.toMatch(/a fact-check changed the result/);
  });

  it("the check FLIPPED the reviewers (pre-floor PASS, final BLOCK): the heading says changed", () => {
    const { container } = renderReport(FLIPPED);
    expect(container.textContent).toMatch(/a fact-check changed the result/);
  });

  it("a recorded pass renders as a confirmation with the values it checked", () => {
    const { container } = renderReport(ESCALATED);
    expect(container.textContent).toMatch(/Confirmed by a fact-check/);
    const pass = screen.getByTestId("floor-pass-row");
    expect(pass.textContent).toMatch(/value_grounding/);
    expect(pass.textContent).toMatch(/4 values? checked/);
    expect(pass.textContent).toMatch(/7:30/);
    expect(pass.textContent).toMatch(/1150/);
  });

  it("no passes recorded → no confirmation section is fabricated", () => {
    const { container } = renderReport(FLAGGED);
    expect(container.textContent).not.toMatch(/Confirmed by a fact-check/);
  });
});
