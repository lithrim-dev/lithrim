/* artifact.test.jsx — A1/A2: the artifact tabs render REAL BFF data (not data.jsx
   mock). JudgeTab takes realized council votes via props; ConfigTab self-fetches GET
   /v1/ontology; CorpusTab self-fetches GET /v1/corpus (populated + empty-state). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// ConfigTab + CorpusTab self-fetch through bff.js — mock the two getters.
vi.mock("./bff.js", () => ({
  getOntology: vi.fn(),
  getCorpus: vi.fn(),
  getCase: vi.fn(),
}));

import { ArtifactPane } from "./artifact.jsx";
import { getOntology, getCorpus, getCase } from "./bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

beforeEach(() => {
  getOntology.mockReset();
  getCorpus.mockReset();
  getCase.mockReset();
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

  it("S-BS-110: an in_process run is labeled PAID (in-process · paid), never replay · $0", () => {
    // Pre-fix the tag was `grade_path === "live" ? "live · paid" : "replay · $0"`, so the
    // LAUNCH-PREP in_process default mislabeled a real PAID run as $0. NON-VACUOUS: pre-fix
    // this asserts the wrong tag and fails.
    const paid = { ...COUNCIL_RESULT, grade_path: "in_process" };
    const { container } = render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runResult={paid} runError={null} />);
    expect(container.textContent).toContain("in-process · paid");
    expect(container.textContent).not.toContain("replay · $0");
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
    expect(screen.getByText("suppress")).toBeInTheDocument();
    expect(screen.getByText(/BLOCK → PASS/)).toBeInTheDocument();
  });

  it("renders a clean empty-state when the corpus is empty (no crash)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    render(<ArtifactPane {...paneProps} tab="corpus" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/No corrections yet/i)).toBeInTheDocument();
  });
});

describe("CaseTab — GET /v1/case, the SOURCE INPUT (CHATBIND-3)", () => {
  it("renders transcript + a JSON artifact (structured) + the planted ground-truth flag", async () => {
    getCase.mockResolvedValue({
      case_id: "bench_scribe_v1_inject_condition",
      transcript: "Dr: Hello Antony.\nPatient: I'm here for a sprain.",
      artifact: JSON.stringify({ resourceType: "DocumentReference", status: "current" }),
      conditions: ["Diabetes mellitus type 2 (disorder)", "Anemia (disorder)"],
      expected_safety_flags: ["FABRICATED_HISTORY"],
      injection_recipe: null,
    });
    render(<ArtifactPane {...paneProps} tab="case" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/here for a sprain/)).toBeInTheDocument(); // the transcript
    expect(screen.getByText("FABRICATED_HISTORY")).toBeInTheDocument(); // the by-construction ground truth
    expect(screen.getByText("structured")).toBeInTheDocument(); // JSON artifact detected + pretty-printed
    expect(screen.getByText(/Diabetes mellitus type 2/)).toBeInTheDocument(); // the patient record
    expect(getCase).toHaveBeenCalledWith("ws0_default"); // self-fetches the ACTIVE agent
  });

  it("renders a free-text artifact + a clean-negative (nothing planted) without crashing", async () => {
    getCase.mockResolvedValue({
      case_id: "imported_scheduling_clean",
      transcript: "Patient calls to book a follow-up.",
      artifact: "Booking confirmed for 2026-07-01 at 10:00.", // free text — NOT json
      conditions: [],
      expected_safety_flags: [],
      injection_recipe: null,
    });
    render(<ArtifactPane {...paneProps} tab="case" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText("free text")).toBeInTheDocument(); // generic: not mis-parsed as JSON
    expect(screen.getByText(/nothing planted/i)).toBeInTheDocument(); // clean negative
    expect(screen.getByText(/Booking confirmed/)).toBeInTheDocument();
  });
});
