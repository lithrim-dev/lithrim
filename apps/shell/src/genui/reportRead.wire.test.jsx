/* reportRead.wire.test.jsx — NARRATIVE-LAYER-1 wiring: the computed "read" band renders on the
   scorecard (band + hero + trust line), the inline verdict card, the Reviewers tab (+ the n/a
   confidence footnote) and the Report pane's "What this means" — and is honestly ABSENT when
   the payload carries nothing to read. All strings computed; nothing hardcoded as data. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getOntology: vi.fn(),
  getCorpus: vi.fn(),
  getCase: vi.fn(),
  listCaseBrowser: vi.fn(),
  recordMetaVerdict: vi.fn(),
  getRunAudit: vi.fn(),
  getCaseReport: vi.fn(),
}));

import ScorecardCard from "./ScorecardCard.jsx";
import VerdictCard from "./VerdictCard.jsx";
import { ArtifactPane } from "../artifact.jsx";
import { getRunAudit, listCaseBrowser, recordMetaVerdict } from "../bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

beforeEach(() => {
  getRunAudit.mockReset();
  getRunAudit.mockResolvedValue({ withstands: [] });
  listCaseBrowser.mockReset();
  listCaseBrowser.mockResolvedValue({ cases: [], count: 0 });
  recordMetaVerdict.mockReset();
  recordMetaVerdict.mockResolvedValue({ status: "ok" });
});

const SCORECARD = {
  cases: [...Array(3).fill("PASS"), ...Array(7).fill("BLOCK"), ...Array(4).fill("WARN")]
    .map((v, i) => ({ case_id: `c${i}`, verdict: v, labeled: true })),
  n_cases: 14, n_labeled: 13,
  flag: { tp: 11, fp: 21, fn: 3, precision: 0.34, recall: 0.79 },
  by_judge: [
    { judge_role: "r1", model: "gpt-4.1", n: 13, matches_gold: 5, misses: 4, over_flags: 4 },
    { judge_role: "r2", model: "claude", n: 13, matches_gold: 6, misses: 3, over_flags: 4 },
    { judge_role: "r3", model: "gemini", n: 13, matches_gold: 4, misses: 5, over_flags: 4 },
  ],
  floor: {
    cleared: 2, enforced: 8, inconclusive: 1, gold_defect_clears: [],
    verdict_accuracy_pre_floor: 0.39, verdict_accuracy_post_floor: 0.54,
  },
};

describe("ScorecardCard — the read band", () => {
  it("renders the band, the reframed hero and the trust line from the real floor payload", () => {
    render(<ScorecardCard {...SCORECARD} />);
    const band = screen.getByTestId("scorecard-read");
    expect(band.textContent).toMatch(/The read/i);
    expect(band.textContent).toMatch(/The gap is the floor doing the work the judges can't\./);
    const hero = screen.getByTestId("scorecard-read-hero");
    expect(hero.textContent).toMatch(/39% → 54%/);
    expect(hero.textContent).toMatch(/reviewers alone → with the floor/);
    expect(screen.getByTestId("scorecard-read-trust").textContent)
      .toBe("0 genuine defects ever cleared · deterministic on every run");
    // everything below stays: the existing floor tallies still render
    expect(screen.getByTestId("scorecard-floor")).toBeInTheDocument();
  });

  it("HONESTY: a genuine-defect clear kills the trust line and says investigate", () => {
    render(<ScorecardCard {...SCORECARD}
      floor={{ ...SCORECARD.floor, gold_defect_clears: [{ case_id: "c9", code: "FABRICATED_CLAIM" }] }} />);
    expect(screen.getByTestId("scorecard-read").textContent).toMatch(/investigate before trusting this run/);
    expect(screen.queryByTestId("scorecard-read-trust")).toBeNull();
  });

  it("renders NO band when the payload has no floor read (honest-absent)", () => {
    render(<ScorecardCard {...SCORECARD} floor={null} />);
    expect(screen.queryByTestId("scorecard-read")).toBeNull();
  });
});

describe("VerdictCard — the read band", () => {
  it("tells the wobble story when the floor enforced what the judges missed", () => {
    render(<VerdictCard verdict="BLOCK" runId="r1"
      votes={[
        { role: "risk_judge", vote: "PASS", confidence: 1.0 },
        { role: "policy_judge", vote: "WARN", confidence: 0.44 },
        { role: "faithfulness_judge", vote: "WARN", confidence: 0.4 },
      ]}
      floorBlocks={[{ flag: "DISSENT_ERASURE", contract_type: "value_presence" }]} />);
    const band = screen.getByTestId("verdict-read");
    expect(band.textContent).toMatch(/On the judges alone this note slips through/);
    expect(band.textContent).toMatch(/The judges wobbled, the floor held\./);
    expect(band.textContent).toMatch(/Dissent erasure/);
  });

  it("renders NO band with no votes and no floor events", () => {
    render(<VerdictCard verdict="approve" agreement="3 / 3" question="Q?" answer="A." runId="r1" />);
    expect(screen.queryByTestId("verdict-read")).toBeNull();
  });
});

describe("JudgeTab — the reviewers read + the n/a-confidence footnote", () => {
  const RUN = {
    case_id: "case_x", grade_path: "replay", pipeline_run_id: "run-x",
    council: {
      votes: [
        { judge_role: "risk_judge", vote: "PASS", confidence: 1.0, model: "gpt-4.1" },
        { judge_role: "policy_judge", vote: "FAIL", confidence: null, model: "gpt-4.1" },
        { judge_role: "faithfulness_judge", vote: "PASS", confidence: 0.8, model: "gpt-4.1" },
      ],
    },
  };

  it("reads the spread in words and footnotes the missing logprob confidence", () => {
    render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runResult={RUN} runError={null} />);
    const band = screen.getByTestId("judges-read");
    expect(band.textContent).toMatch(/One of three reviewers voted to block, two passed outright\./);
    expect(band.textContent).toMatch(/confidence reads n\/a where the model doesn't expose token logprobs/);
  });

  it("omits the footnote when every vote carries a confidence", () => {
    const allConf = { ...RUN, council: { votes: RUN.council.votes.map((v) => ({ ...v, confidence: 0.9 })) } };
    render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runResult={allConf} runError={null} />);
    expect(screen.getByTestId("judges-read").textContent).not.toMatch(/token logprobs/);
  });
});

describe("ReportTab — the read band atop 'What this means'", () => {
  const FLOOR_ENFORCED_RUN = {
    case_id: "case_floor_enforced", grade_path: "in_process", pipeline_run_id: "run-fe",
    composite: {
      verdict: "reject", stage_verdict: "BLOCK", score: 1,
      active_findings: ["DISSENT_ERASURE"],
      grounded_adjustments: [],
      floor_adjustments: [
        { flag: "DISSENT_ERASURE", action: "floor_block", contract_type: "value_presence", contract: "v1", conforms: false, disposition: "refusal missing from the note" },
        { flag: "WRONG_DOSAGE", action: "floor_inconclusive", contract_type: "dose-range", contract: "v1", conforms: null, disposition: "tool unreachable" },
      ],
    },
    council: {
      case_outcome: "FLAGGED",
      votes: [
        { judge_role: "risk_judge", vote: "PASS", confidence: 1.0 },
        { judge_role: "policy_judge", vote: "WARN", confidence: 0.4 },
      ],
    },
    calibration_check: { label_status: "unlabeled", n_cases: 1 },
  };

  it("tells the enforcement story counting ONLY floor_block rows (inconclusive never counted)", () => {
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={FLOOR_ENFORCED_RUN} runError={null} />);
    const band = screen.getByTestId("report-read");
    expect(band.textContent).toMatch(/1 deterministic fact-check found Dissent erasure/);
    expect(band.textContent).toMatch(/The judges wobbled, the floor held\./);
    expect(band.textContent).not.toMatch(/2 deterministic fact-checks/);
    // the existing summary below stays
    expect(screen.getByTestId("report-summary").textContent).toMatch(/What this means|a person should|review this/i);
  });

  it("renders NO band on a run with no votes and no floor events", () => {
    const bare = {
      ...FLOOR_ENFORCED_RUN,
      composite: { ...FLOOR_ENFORCED_RUN.composite, verdict: "approve", stage_verdict: "PASS", score: 0, active_findings: [], floor_adjustments: [] },
      council: { case_outcome: "CLEAR", votes: [] },
    };
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={bare} runError={null} />);
    expect(screen.queryByTestId("report-read")).toBeNull();
    expect(screen.getByTestId("report-summary")).toBeInTheDocument();
  });
});
