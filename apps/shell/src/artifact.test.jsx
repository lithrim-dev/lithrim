/* artifact.test.jsx — A1/A2: the artifact tabs render REAL BFF data (not data.jsx
   mock). JudgeTab takes realized council votes via props; ConfigTab self-fetches GET
   /v1/ontology; CorpusTab self-fetches GET /v1/corpus (populated + empty-state). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ConfigTab + CorpusTab self-fetch through bff.js — mock the getters + the meta-verdict write.
vi.mock("./bff.js", () => ({
  getOntology: vi.fn(),
  getCorpus: vi.fn(),
  getCase: vi.fn(),
  listCases: vi.fn(),
  recordMetaVerdict: vi.fn(),
}));

import { ArtifactPane } from "./artifact.jsx";
import { getOntology, getCorpus, getCase, listCases, recordMetaVerdict } from "./bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

beforeEach(() => {
  getOntology.mockReset();
  getCorpus.mockReset();
  getCase.mockReset();
  listCases.mockReset();
  listCases.mockResolvedValue({ cases: [], count: 0 }); // default: no ingested cases
  recordMetaVerdict.mockReset();
});

const COUNCIL_RESULT = {
  case_id: "bench_scribe_v1_inject_condition_1bd0f10dc7b5",
  grade_path: "replay",
  council: {
    votes: [
      { judge_role: "risk_judge", vote: "PASS", confidence: 1.0, model: "gpt-4.1", reason: "no HIPAA issue" },
      { judge_role: "policy_judge", vote: "FAIL", confidence: null, model: "gpt-4.1", reason: "fabricated history" },
      { judge_role: "faithfulness_judge", vote: "PASS", confidence: 0.8, model: "gpt-4.1", reason: "" },
    ],
    configured: ["risk_judge"],
  },
};

describe("JudgeTab — realized council votes (A1)", () => {
  it("renders the per-judge votes threaded via props (not data.jsx JUDGES)", () => {
    render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runResult={COUNCIL_RESULT} runError={null} />);
    expect(screen.getByText("risk_judge")).toBeInTheDocument();
    expect(screen.getByText("policy_judge")).toBeInTheDocument();
    expect(screen.getByText("faithfulness_judge")).toBeInTheDocument();
    expect(screen.getByText("1 blocking vote(s)")).toBeInTheDocument(); // the FAIL
    // confidence:null tolerated (WS-6a D-E) — rendered as n/a, not a crash
    expect(screen.getByText(/confidence n\/a/)).toBeInTheDocument();
  });

  it("S-BS-110: an in_process run is labeled PAID (Full run · paid), never a $0 preview", () => {
    // An in_process run is a real PAID council run — it must never be mislabeled as a $0 preview.
    // NON-VACUOUS: if the in_process tag regressed to the replay/$0 label, this fails.
    const paid = { ...COUNCIL_RESULT, grade_path: "in_process" };
    const { container } = render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runResult={paid} runError={null} />);
    expect(container.textContent).toContain("Full run · paid");
    expect(container.textContent).not.toContain("· $0");
  });

  it("prompts to run when there is no run yet", () => {
    render(<ArtifactPane {...paneProps} tab="judges" runStatus="idle" runResult={null} runError={null} />);
    expect(screen.getByText(/per-case votes/i)).toBeInTheDocument();
  });
});

describe("ConfigTab — ontology config from GET /v1/ontology (A1)", () => {
  it("renders the real ontology config (domain, flags, severity, contracts)", async () => {
    getOntology.mockResolvedValue({
      domain: "clinical",
      ontology_version: "clinical/1",
      severity_map: { block_at_or_above: 1.0, warn_above: 0, weights: { HIGH: 1, MEDIUM: 0.5, LOW: 0.2 } },
      flags: [
        { flag: "FABRICATED_ALLERGY", tier: "TIER_1", gradeable: true, owner_roles: ["risk_judge"] },
        { flag: "FABRICATED_CONSENT_SCOPE", tier: null, gradeable: false, owner_roles: [] },
      ],
      verification_contracts: [
        { flag_code: "MEDICATION_NOT_IN_TRANSCRIPT", contract_type: "presence_check", version: "med-presence-check/v1", question: "present?" },
      ],
    });
    render(<ArtifactPane {...paneProps} tab="config" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/clinical · clinical\/1/)).toBeInTheDocument();
    expect(screen.getByText("FABRICATED_ALLERGY")).toBeInTheDocument();
    expect(screen.getByText("gradeable")).toBeInTheDocument();
    expect(screen.getByText("reference")).toBeInTheDocument(); // the non-gradeable flag
    expect(screen.getByText("MEDICATION_NOT_IN_TRANSCRIPT")).toBeInTheDocument(); // contract
  });

  it("CHATBIND-2: fetches the ACTIVE agent's ontology (the agent thread), not ws0_default", async () => {
    // The approved deviation: ArtifactPane threads `agent` (= activeAgent) to ConfigTab so the
    // chat-driven "show its config" loads the SELECTED case's ontology. NON-VACUOUS — pre-thread
    // ConfigTab self-fetched the hardcoded ws0_default, and this getOntology arg assertion fails.
    getOntology.mockResolvedValue({
      domain: "radiology",
      ontology_version: "radiology/1",
      severity_map: { block_at_or_above: 1.0, warn_above: 0, weights: {} },
      flags: [],
    });
    render(<ArtifactPane {...paneProps} tab="config" agent="imported_case_42" runStatus="idle" runResult={null} runError={null} />);
    await screen.findByText(/radiology · radiology\/1/);
    expect(getOntology).toHaveBeenCalledWith("imported_case_42");
  });
});

describe("CorpusTab — GET /v1/corpus (A2)", () => {
  it("renders corpus-row/1 rows when populated", async () => {
    getCorpus.mockResolvedValue({
      rows: [
        {
          case_id: "bench_scribe_v1", action: "suppress", flag_code: "MEDICATION_NOT_IN_TRANSCRIPT",
          verdict_before: "BLOCK", verdict_after: "PASS", contract: "med-presence-check/v1",
          owner_roles: ["risk_judge"], rollout_ref: "abc123def456",
        },
      ],
    });
    render(<ArtifactPane {...paneProps} tab="corpus" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText("MEDICATION_NOT_IN_TRANSCRIPT")).toBeInTheDocument();
    expect(screen.getByText("false alarm cleared")).toBeInTheDocument();
    expect(screen.getByText(/BLOCK → PASS/)).toBeInTheDocument();
  });

  it("renders a clean empty-state when the corpus is empty (no crash)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    render(<ArtifactPane {...paneProps} tab="corpus" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/No corrections yet/i)).toBeInTheDocument();
  });

  it("NARR-LOOP: the Corpus tab self-fetches the INGESTED cases so they survive a reload", async () => {
    // the refresh-poof fix: GET /v1/cases is fetched on mount, independent of any chat session.
    getCorpus.mockResolvedValue({ rows: [] });
    listCases.mockResolvedValue({
      count: 2,
      cases: [
        { case_id: "clinverdict_01_neurology", labeled: false, has_context: true, has_artifact: true },
        { case_id: "clinverdict_10_splinter", labeled: false, has_context: false, has_artifact: true },
      ],
    });
    render(<ArtifactPane {...paneProps} tab="corpus" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText("clinverdict_01_neurology")).toBeInTheDocument();
    expect(screen.getByText("clinverdict_10_splinter")).toBeInTheDocument();
    expect(screen.getByText(/2 ingested · 1 with transcript/)).toBeInTheDocument(); // fidelity signal
    expect(screen.getByText("transcript ✓")).toBeInTheDocument(); // case 01 carries its transcript
  });
});

describe("CaseTab — GET /v1/case, the SOURCE INPUT (CHATBIND-3)", () => {
  it("renders transcript + a JSON artifact (structured) + the planted ground-truth flag", async () => {
    getCase.mockResolvedValue({
      case_id: "bench_scribe_v1_inject_condition",
      transcript: "Dr: Hello Antony.\nPatient: I'm here for a sprain.",
      artifact: JSON.stringify({ resourceType: "DocumentReference", status: "current" }),
      artifact_text: "SUBJECTIVE: 28M presents for sprain.", // the decoded readable note
      conditions: ["Diabetes mellitus type 2 (disorder)", "Anemia (disorder)"],
      expected_safety_flags: ["FABRICATED_HISTORY"],
      injection_recipe: null,
    });
    render(<ArtifactPane {...paneProps} tab="case" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/here for a sprain/)).toBeInTheDocument(); // the transcript
    expect(screen.getByText(/SUBJECTIVE: 28M presents/)).toBeInTheDocument(); // the readable note (decoded)
    expect(screen.getByText("FABRICATED_HISTORY")).toBeInTheDocument(); // the by-construction ground truth
    expect(screen.getByText("raw · structured")).toBeInTheDocument(); // a note present -> the artifact is the raw view
    expect(screen.getByText(/Diabetes mellitus type 2/)).toBeInTheDocument(); // the patient record
    expect(getCase).toHaveBeenCalledWith("ws0_default", null); // active agent · no specific case selected
  });

  it("renders a free-text artifact + a clean-negative (nothing planted) without crashing", async () => {
    getCase.mockResolvedValue({
      case_id: "imported_scheduling_clean",
      transcript: "Patient calls to book a follow-up.",
      artifact: "Booking confirmed for 2026-07-01 at 10:00.", // free text — NOT json
      conditions: [],
      expected_safety_flags: [],
      injection_recipe: null,
      labeled: true, // HONEST-1: a DECLARED clean-negative (label present, empty)
    });
    render(<ArtifactPane {...paneProps} tab="case" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText("free text")).toBeInTheDocument(); // generic: not mis-parsed as JSON
    expect(screen.getByText(/nothing planted/i)).toBeInTheDocument(); // clean negative
    expect(screen.getByText(/Booking confirmed/)).toBeInTheDocument();
  });

  // A5 — HONEST-1: an UNLABELED (BYO) case must not be mislabeled as a clean negative.
  it("an unlabeled case (labeled:false) reads 'No planted answer', NOT 'nothing planted'", async () => {
    getCase.mockResolvedValue({
      case_id: "byo_note_1",
      transcript: "Patient calls to book a follow-up.",
      artifact: "Booking confirmed.",
      conditions: [],
      labeled: false, // BYO/ingested: no planted label — the serializer marks it unlabeled
    });
    render(<ArtifactPane {...paneProps} tab="case" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/No planted answer/i)).toBeInTheDocument();
    expect(screen.queryByText(/nothing planted/i)).toBeNull();
    expect(screen.queryByText(/expected verdict: approve/i)).toBeNull();
  });
});

// A4 — HONEST-1: the Report/Calibration block must withhold accuracy/ECE on unlabeled
// data (no fabricated 0.0/WARN), while the verdict + grounding still render (label-free).
const UNLABELED_RUN = {
  case_id: "byo_note_1",
  grade_path: "in_process",
  composite: {
    verdict: "reject",
    stage_verdict: "BLOCK",
    score: 1.0,
    active_findings: ["FABRICATED_HISTORY"],
    grounded_adjustments: [],
  },
  calibration_check: {
    label_status: "unlabeled",
    status: "unlabeled",
    verdict_match_rate: null,
    ece: null,
    n_cases: 1,
    n_with_confidence: 0,
    caveat: "no ground truth — verdict + grounding shown; author labels to unlock accuracy/calibration",
  },
};

describe("ReportTab — HONEST-1 unlabeled mode (A4)", () => {
  it("withholds accuracy/ECE on unlabeled data — no fake 0.0/WARN, verdict still shown", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={UNLABELED_RUN} runError={null} />,
    );
    // the verdict + finding still render (label-free, real)
    expect(screen.getByText("FABRICATED_HISTORY")).toBeInTheDocument();
    // honest copy — NOT a fabricated accuracy number
    expect(screen.getByText(/accuracy can.t be measured yet/i)).toBeInTheDocument();
    expect(container.textContent).not.toContain("WARN");
    expect(container.textContent).not.toContain("· PASS");
    expect(container.textContent).not.toContain("null ·");
  });
});

// NARR-5 D2 — the ReportTab Floor Blocks section. composite() emits `floor_adjustments`
// (report.py:87) but artifact.jsx rendered it NOWHERE; the SILENT_DEGRADATION floor flip
// (PASS→BLOCK→reject) was invisible. Each adj = {flag, action: floor_block|floor_inconclusive,
// contract_type, contract, conforms, disposition}.
const FLOOR_BLOCK_RUN = {
  case_id: "narrative_jinn_silent_degradation",
  grade_path: "in_process",
  composite: {
    verdict: "reject",
    stage_verdict: "BLOCK",
    score: 1.0,
    active_findings: ["SILENT_DEGRADATION"],
    grounded_adjustments: [],
    floor_adjustments: [
      {
        flag: "SILENT_DEGRADATION",
        action: "floor_block",
        contract_type: "silent_degradation",
        contract: "v1",
        conforms: false,
        disposition: "inject_block",
      },
    ],
    floor_block_count: 1,
  },
  calibration_check: { label_status: "unlabeled", status: "unlabeled", verdict_match_rate: null, ece: null, n_cases: 1, n_with_confidence: 0 },
};

const NO_FLOOR_RUN = {
  case_id: "narrative_jinn_exposure_clean",
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

describe("ReportTab — Floor Blocks section (NARR-5 D2)", () => {
  it("renders a floor_block (SILENT_DEGRADATION verdict-flip) with its contract + disposition", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={FLOOR_BLOCK_RUN} runError={null} />,
    );
    expect(screen.getByText(/Hard-rule failures/i)).toBeInTheDocument();
    // the flag code, contract type, and disposition all render
    const flagHits = screen.getAllByText("SILENT_DEGRADATION");
    expect(flagHits.length).toBeGreaterThan(0);
    expect(container.textContent).toContain("silent_degradation"); // contract_type
    expect(container.textContent).toContain("inject_block"); // disposition
  });

  it("does NOT render a Floor blocks section (no false BLOCK styling) when floor_adjustments is empty", () => {
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={NO_FLOOR_RUN} runError={null} />);
    expect(screen.queryByText(/Hard-rule failures/i)).toBeNull();
  });
});

// META-VERDICT-1: the clinician's INDEPENDENT verdict + judge meta-audit (ClinVerdict Layer-3).
describe("ReportTab — clinician verdict (META-VERDICT-1)", () => {
  const REPORT_RESULT = {
    case_id: "clinverdict_10",
    grade_path: "replay",
    pipeline_run_id: "run-xyz",
    composite: {
      verdict: "approve",
      stage_verdict: "PASS",
      score: 0.2,
      active_findings: [],
      grounded_adjustments: [],
      floor_adjustments: [],
    },
    calibration_check: { label_status: "unlabeled", n_cases: 1 },
  };

  it("records a DISSENT (fail + named fallacy) against the run via POST /v1/meta-verdict", async () => {
    recordMetaVerdict.mockResolvedValue({ status: "ok" });
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={REPORT_RESULT} runError={null} />);
    expect(screen.getByTestId("clinician-verdict")).toBeInTheDocument();
    // verdict defaults to "fail" (dissent); name the fallacy + rationale, then record.
    fireEvent.change(screen.getByLabelText("Judge fallacy"), { target: { value: "Reference Bias" } });
    fireEvent.change(screen.getByLabelText("Rationale"), { target: { value: "ref note omitted the dissent" } });
    fireEvent.click(screen.getByText("Record verdict"));
    await waitFor(() => expect(recordMetaVerdict).toHaveBeenCalledTimes(1));
    expect(recordMetaVerdict).toHaveBeenCalledWith({
      run_id: "run-xyz",
      human_verdict: "fail",
      agrees_with_council: false,
      judge_fallacy_code: "Reference Bias",
      rationale: "ref note omitted the dissent",
    });
    expect(await screen.findByText("Recorded ✓")).toBeInTheDocument(); // the button flips to confirmed
  });

  it("AGREEING with the council hides the fallacy picker and omits the code", async () => {
    recordMetaVerdict.mockResolvedValue({ status: "ok" });
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={REPORT_RESULT} runError={null} />);
    fireEvent.click(screen.getByLabelText(/I agree with the council/));
    expect(screen.queryByLabelText("Judge fallacy")).toBeNull(); // the picker is gone
    fireEvent.click(screen.getByText("Pass"));
    fireEvent.click(screen.getByText("Record verdict"));
    await waitFor(() => expect(recordMetaVerdict).toHaveBeenCalledTimes(1));
    const payload = recordMetaVerdict.mock.calls[0][0];
    expect(payload.agrees_with_council).toBe(true);
    expect(payload.human_verdict).toBe("pass");
    expect("judge_fallacy_code" in payload).toBe(false); // never sent when agreeing
  });

  it("no run yet (no pipeline_run_id) → prompts to run first, never POSTs", () => {
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready"
      runResult={{ ...REPORT_RESULT, pipeline_run_id: undefined }} runError={null} />);
    expect(screen.getByText(/Run an evaluation first/)).toBeInTheDocument();
    expect(recordMetaVerdict).not.toHaveBeenCalled();
  });
});
