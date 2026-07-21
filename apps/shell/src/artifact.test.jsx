/* artifact.test.jsx — A1/A2: the artifact tabs render REAL BFF data (not data.jsx
   mock). JudgeTab takes realized council votes via props; ConfigTab self-fetches GET
   /v1/ontology; CorpusTab self-fetches GET /v1/corpus (populated + empty-state). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ConfigTab + CorpusTab + JudgeTab self-fetch through bff.js — mock the getters + the meta-verdict write.
vi.mock("./bff.js", () => ({
  getOntology: vi.fn(),
  getCorpus: vi.fn(),
  getCase: vi.fn(),
  listCaseBrowser: vi.fn(),
  recordMetaVerdict: vi.fn(),
  getRunAudit: vi.fn(),
}));

import { ArtifactPane } from "./artifact.jsx";
import { getOntology, getCorpus, getCase, listCaseBrowser, recordMetaVerdict, getRunAudit } from "./bff.js";

const paneProps = { width: 440, full: false, setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

beforeEach(() => {
  getOntology.mockReset();
  getCorpus.mockReset();
  getCase.mockReset();
  listCaseBrowser.mockReset();
  listCaseBrowser.mockResolvedValue({ cases: [], count: 0 }); // default: nothing to browse
  recordMetaVerdict.mockReset();
  getRunAudit.mockReset();
  getRunAudit.mockResolvedValue({ withstands: [] }); // default: no lens unless a test provides one
});

const COUNCIL_RESULT = {
  case_id: "bench_scribe_v1_inject_condition_1bd0f10dc7b5",
  grade_path: "replay",
  pipeline_run_id: "run-xyz", // JudgeTab self-fetches the lens from GET /v1/runs/{id}/audit
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
  it("renders the per-reviewer votes threaded via props (not data.jsx JUDGES), names via copy.js", () => {
    render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runResult={COUNCIL_RESULT} runError={null} />);
    expect(screen.getByText("Risk reviewer")).toBeInTheDocument(); // risk_judge → roleLabel
    expect(screen.getByText("Policy reviewer")).toBeInTheDocument();
    expect(screen.getByText("Faithfulness reviewer")).toBeInTheDocument();
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
    expect(screen.getByText(/how each reviewer voted/i)).toBeInTheDocument();
  });

  // TRANSPARENCY-1 (the Clinical Scribe Review contrast): the Judges pane shows each judge's LENS — the
  // flags it could raise — self-fetched from GET /v1/runs/{id}/audit (`withstands`). So a PASS
  // that happened because NOTHING in the lens covers the defect (Risk-Severity Blindness) is
  // VISIBLE, not inferred. This is the "why did it miss?" beat.
  it("shows each judge's lens (the flags it can flag), fetched from the run audit", async () => {
    getRunAudit.mockResolvedValue({
      withstands: [
        { role: "risk_judge", signals_weighed: { ontology_rules: [
          { code: "WRONG_DOSAGE", in_lens: true, raised: false },
          { code: "MISSED_ESCALATION", in_lens: true, raised: false },
          { code: "OUT_OF_LENS", in_lens: false, raised: false },
        ] } },
        { role: "policy_judge", signals_weighed: { ontology_rules: [
          { code: "FABRICATED_CONSENT", in_lens: true, raised: false },
        ] } },
        { role: "faithfulness_judge", signals_weighed: { ontology_rules: [
          { code: "HISTORY_OMISSION", in_lens: true, raised: false },
        ] } },
      ],
    });
    const { container } = render(
      <ArtifactPane {...paneProps} tab="judges" runStatus="ready" runResult={COUNCIL_RESULT} runError={null} />,
    );
    // the JudgeTab self-fetched the lens by the run id
    await waitFor(() => expect(getRunAudit).toHaveBeenCalledWith("run-xyz"));
    // the flags in each reviewer's lens render (what it COULD have raised), relabeled via flagLabel —
    // the out-of-lens one does not
    await waitFor(() => expect(screen.getByText("Wrong dosage")).toBeInTheDocument());
    expect(screen.getByText("Missed escalation")).toBeInTheDocument();
    expect(screen.getByText("Fabricated consent")).toBeInTheDocument();
    expect(screen.queryByText("Out of lens")).toBeNull(); // in_lens=false is excluded
    expect(container.querySelectorAll(".judge-lens").length).toBe(3);
    expect(container.textContent).toMatch(/raised none/i); // the blind spot, named
  });
});

// Full judge reasoning in the Reviewers cards: reward-model judges emit `explanation` where LLM
// judges emit `reason` — one normalized read; the clipped line carries the FULL text as a tooltip
// and click-expands; a vote carrying a non-empty `errors` array is an ERRORED judge, rendered as a
// distinct state (red tag + first error line), never as a considered vote.
describe("JudgeTab — full reasoning (tooltip + expand) + judge-error state", () => {
  const LONG_WHY =
    "The note asserts a penicillin allergy that never appears in the transcript, and the dosage on line 4 contradicts the stated plan of care entirely.";
  const withVotes = (votes) => ({ case_id: "case-1", grade_path: "replay", council: { votes, configured: [] } });

  it("normalizes reward-model `explanation` like LLM `reason` (both render)", () => {
    render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runError={null}
      runResult={withVotes([
        { judge_role: "risk_judge", vote: "PASS", confidence: 0.9, model: "gpt-4.1", reason: "short llm reason" },
        { judge_role: "reward_judge", vote: "WARN", confidence: 0.5, model: "rm-1", explanation: "short rm explanation" },
      ])} />);
    expect(screen.getByText("short llm reason")).toBeInTheDocument();
    expect(screen.getByText("short rm explanation")).toBeInTheDocument();
  });

  it("clips a long reason with the full text as tooltip; click expands, second click collapses", () => {
    render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runError={null}
      runResult={withVotes([{ judge_role: "risk_judge", vote: "PASS", confidence: 0.9, model: "gpt-4.1", reason: LONG_WHY }])} />);
    const line = screen.getByTitle(LONG_WHY);
    expect(line.textContent).toBe(LONG_WHY.slice(0, 80) + "…"); // clipped, tooltip = full text
    fireEvent.click(line);
    expect(screen.getByTitle(LONG_WHY).textContent).toBe(LONG_WHY); // expanded: the full text
    fireEvent.click(screen.getByTitle(LONG_WHY));
    expect(screen.getByTitle(LONG_WHY).textContent).toBe(LONG_WHY.slice(0, 80) + "…"); // collapsed again
  });

  it("a vote with `errors` renders the errored tag + first error line, NOT a considered vote", () => {
    const { container } = render(<ArtifactPane {...paneProps} tab="judges" runStatus="ready" runError={null}
      runResult={withVotes([{ judge_role: "risk_judge", vote: "WARN", confidence: 0.5, model: "rm-1",
        errors: ["ProviderTimeout: judge call failed", "retry exhausted"] }])} />);
    const chip = screen.getByText("errored");
    expect(chip.className).toMatch(/\btag\b/);
    expect(chip.className).toMatch(/\bfail\b/);
    expect(screen.getByText(/ProviderTimeout: judge call failed/)).toBeInTheDocument(); // the first error line
    expect(screen.queryByText("Needs a look")).toBeNull(); // the WARN is not presented as considered
    expect(container.textContent).not.toContain("retry exhausted"); // only the FIRST line
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
    expect(screen.getByText("Fabricated allergy")).toBeInTheDocument(); // FABRICATED_ALLERGY → flagLabel
    expect(screen.getByText("scored")).toBeInTheDocument(); // gradeable flag, plainer label
    expect(screen.getByText("reference")).toBeInTheDocument(); // the non-gradeable flag
    expect(screen.getByText("Medication not in transcript")).toBeInTheDocument(); // contract → flagLabel
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

  // F3: before this workspace has its own evaluation, GET /v1/ontology resolves the leaked
  // `_core` seed sample — so a non-`_core` workspace must NOT mislabel its Setup as "generic ·
  // _core/1". The stale domain·version chip is suppressed until a real ontology resolves.
  it("F3: suppresses the misleading `generic · _core/1` chip in a non-_core workspace", async () => {
    getOntology.mockResolvedValue({
      domain: "generic",
      ontology_version: "_core/1",
      severity_map: { block_at_or_above: 1.0, warn_above: 0, weights: {} },
      flags: [],
    });
    render(<ArtifactPane {...paneProps} tab="config" wsPack="clinverdict" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByTestId("config-domain-pending")).toBeInTheDocument();
    expect(screen.queryByText(/generic · _core\/1/)).not.toBeInTheDocument();
  });

  // F3 (non-vacuous): on the `_core` workspace, `_core/1` is the REAL ontology — show it, no suppress.
  it("F3: still shows `_core/1` when the workspace itself pins _core", async () => {
    getOntology.mockResolvedValue({
      domain: "generic",
      ontology_version: "_core/1",
      severity_map: { block_at_or_above: 1.0, warn_above: 0, weights: {} },
      flags: [],
    });
    render(<ArtifactPane {...paneProps} tab="config" wsPack="_core" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/generic · _core\/1/)).toBeInTheDocument();
    expect(screen.queryByTestId("config-domain-pending")).not.toBeInTheDocument();
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
    expect(await screen.findByText("Medication not in transcript")).toBeInTheDocument(); // flag_code → flagLabel
    expect(screen.getByText("false alarm cleared")).toBeInTheDocument();
    expect(screen.getByText(/Flagged → Passed/)).toBeInTheDocument(); // BLOCK→PASS relabeled via verdictLabel
  });

  it("renders a clean empty-state when the corpus is empty (no crash)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    render(<ArtifactPane {...paneProps} tab="corpus" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/No corrections yet/i)).toBeInTheDocument();
  });

  // CASE-BROWSER-1 (UI-pass 2026-07-04 finding #1): the Cases tab is the case-DISCOVERY surface —
  // every loadable case (pinned source + pack fixtures + ingested), each row carrying the
  // by-construction label, this agent's run count, and the baseline-freshness dot. Self-fetched
  // (GET /v1/cases/browser) so it survives a reload, independent of any chat session.
  it("CASE-BROWSER-1: lists every loadable case with its label chip, run count and baseline dot", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue({
      agent: "ws0_default", count: 3, truncated: false,
      cases: [
        { case_id: "case_a_defect", source: "pinned", labeled: true, defect: "FABRICATED_CLAIM", runs: 2, baseline: "fresh" },
        { case_id: "case_b_clean", source: "pinned", labeled: true, defect: null, runs: 1, baseline: "stale" },
        { case_id: "case_c_ingested", source: "ingested", labeled: false, defect: null, runs: 0, baseline: "none" },
      ],
    });
    render(<ArtifactPane {...paneProps} tab="corpus" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText("case_a_defect")).toBeInTheDocument();
    expect(screen.getByText("Fabricated claim")).toBeInTheDocument(); // the defect chip via flagLabel
    expect(screen.getByText("clean")).toBeInTheDocument(); // labeled + nothing planted = clean negative
    expect(screen.getByText("unlabeled")).toBeInTheDocument(); // BYO data: unknown ground truth, honest
    expect(screen.getByText(/2 runs/)).toBeInTheDocument();
    // the baseline dot is title-explained, never a bare colored circle
    expect(screen.getByTitle(/baseline: fresh/i)).toBeInTheDocument();
    expect(screen.getByTitle(/baseline: stale/i)).toBeInTheDocument();
    expect(screen.getByTitle(/no saved baseline/i)).toBeInTheDocument();
  });

  it("CASE-BROWSER-1: clicking a row selects the case for the Run buttons (onSelectCase)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue({
      cases: [{ case_id: "case_a_defect", source: "pinned", labeled: true, defect: "FABRICATED_CLAIM", runs: 0, baseline: "none" }],
      count: 1,
    });
    const onSelectCase = vi.fn();
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={onSelectCase} runStatus="idle" runResult={null} runError={null} />);
    fireEvent.click(await screen.findByText("case_a_defect"));
    expect(onSelectCase).toHaveBeenCalledWith("case_a_defect");
  });

  it("CASE-BROWSER-1: an empty browser says how to load cases (not a silent blank)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue({ cases: [], count: 0 });
    render(<ArtifactPane {...paneProps} tab="corpus" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/No cases to browse yet/i)).toBeInTheDocument();
  });
});

// COHORT-SUBSET-1 (feat/cohort-and-subset-ui): the Cases browser gets MULTI-SELECT + a
// "Run selected (N)" cohort trigger, closing the one-or-all/chat-only gap. Selection is a Set
// lifted into shared state; the row-body click still ARMS a single case (unchanged default);
// a per-row checkbox toggles cohort membership. "Run selected (N)" is hidden on an empty set and,
// on click, dispatches the SAME cohort cost-confirm the chat's propose_run_all opens — carrying
// the selected case_ids (the existing subset-capable gradeCases param). No paid call from the pane.
describe("CaseBrowserSection — multi-select cohort (COHORT-SUBSET-1)", () => {
  const THREE = {
    agent: "ws0_default", count: 3, truncated: false,
    cases: [
      { case_id: "case_a", source: "pinned", labeled: true, defect: "FABRICATED_CLAIM", runs: 0, baseline: "none" },
      { case_id: "case_b", source: "pinned", labeled: true, defect: null, runs: 0, baseline: "none" },
      { case_id: "case_c", source: "ingested", labeled: false, defect: null, runs: 0, baseline: "none" },
    ],
  };

  it("empty selection: no 'Run selected' button — single-arm behavior is unchanged (row click still arms)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue(THREE);
    const onSelectCase = vi.fn();
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={onSelectCase} selectedIds={new Set()} onToggleSelect={vi.fn()} runStatus="idle" runResult={null} runError={null} />);
    await screen.findByText("case_a");
    expect(screen.queryByTestId("run-selected")).toBeNull(); // hidden on empty set
    fireEvent.click(screen.getByText("case_a")); // row body still arms a single case
    expect(onSelectCase).toHaveBeenCalledWith("case_a");
  });

  it("toggling a checkbox calls onToggleSelect(case_id) without arming (independent of single-select)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue(THREE);
    const onSelectCase = vi.fn();
    const onToggleSelect = vi.fn();
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={onSelectCase} selectedIds={new Set()} onToggleSelect={onToggleSelect} runStatus="idle" runResult={null} runError={null} />);
    await screen.findByText("case_a");
    fireEvent.click(screen.getByTestId("case-check-case_b"));
    expect(onToggleSelect).toHaveBeenCalledWith("case_b");
    expect(onSelectCase).not.toHaveBeenCalled(); // toggling membership must NOT arm the single case
  });

  it("a non-empty selection shows 'Run selected (N)' and, on click, dispatches lithrim:grade-cohort with the selected case_ids", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue(THREE);
    const heard = [];
    const onHear = (e) => heard.push(e.detail);
    window.addEventListener("lithrim:grade-cohort", onHear);
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={vi.fn()} selectedIds={new Set(["case_a", "case_c"])} onToggleSelect={vi.fn()} runStatus="idle" runResult={null} runError={null} />);
    const btn = await screen.findByTestId("run-selected");
    expect(btn.textContent).toMatch(/Run selected \(2\)/);
    fireEvent.click(btn);
    window.removeEventListener("lithrim:grade-cohort", onHear);
    expect(heard).toHaveLength(1);
    expect(new Set(heard[0].case_ids)).toEqual(new Set(["case_a", "case_c"]));
  });

  it("a selected row is visually checked (checkbox reflects the lifted Set)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue(THREE);
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={vi.fn()} selectedIds={new Set(["case_b"])} onToggleSelect={vi.fn()} runStatus="idle" runResult={null} runError={null} />);
    await screen.findByText("case_a");
    expect(screen.getByTestId("case-check-case_b").checked).toBe(true);
    expect(screen.getByTestId("case-check-case_a").checked).toBe(false);
  });

  // COHORT-SELECT-ALL-1 (2026-07-19, live pain at 187 cases): selecting a large cohort meant
  // clicking every checkbox, then scrolling back up to a header that had scrolled away. The
  // header (with Run selected) is STICKY inside the .art-bd scroller, and a Select all / Clear
  // toggle bulk-drives the SAME lifted-Set path (one onToggleSelect per id — the App's functional
  // setState composes them; no new selection API, no pane-owned state).
  it("Select all toggles every UNCHECKED listed case through onToggleSelect (never the checked ones)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue(THREE);
    const onToggleSelect = vi.fn();
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={vi.fn()} selectedIds={new Set(["case_b"])} onToggleSelect={onToggleSelect} runStatus="idle" runResult={null} runError={null} />);
    await screen.findByText("case_a");
    const btn = screen.getByTestId("select-all");
    expect(btn.textContent).toMatch(/Select all \(3\)/);
    fireEvent.click(btn);
    expect(new Set(onToggleSelect.mock.calls.map((c) => c[0]))).toEqual(new Set(["case_a", "case_c"]));
  });

  it("with every case selected the button reads Clear and unselects them all", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue(THREE);
    const onToggleSelect = vi.fn();
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={vi.fn()} selectedIds={new Set(["case_a", "case_b", "case_c"])} onToggleSelect={onToggleSelect} runStatus="idle" runResult={null} runError={null} />);
    await screen.findByText("case_a");
    const btn = screen.getByTestId("select-all");
    expect(btn.textContent).toMatch(/Clear/);
    fireEvent.click(btn);
    expect(new Set(onToggleSelect.mock.calls.map((c) => c[0]))).toEqual(new Set(["case_a", "case_b", "case_c"]));
  });

  it("the Cases header (carrying Run selected) is sticky so the button never scrolls away", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue(THREE);
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={vi.fn()} selectedIds={new Set(["case_a"])} onToggleSelect={vi.fn()} runStatus="idle" runResult={null} runError={null} />);
    await screen.findByText("case_a");
    const header = screen.getByTestId("cases-header");
    expect(header.style.position).toBe("sticky");
    // -18px, NOT 0: Chrome insets the sticky constraint by .art-bd's 18px padding while rows
    // stay visible through that strip — a 0 pin floats the header with rows bleeding above it
    // (the v0.1.7 regression, verified live before this pin).
    expect(header.style.top).toBe("-18px");
    expect(header).toContainElement(screen.getByTestId("run-selected"));
    expect(header).toContainElement(screen.getByTestId("select-all"));
    // the instruction rides its OWN wrapped line under the title row (it ran beneath the
    // buttons when it shared their nowrap row), still inside the sticky band
    expect(header).toContainElement(screen.getByTestId("cases-hint"));
    expect(screen.getByTestId("cases-hint").textContent).toMatch(/check to grade several/);
  });

  it("the padded checkbox zone toggles WITHOUT arming (a near-miss must not open the case)", async () => {
    getCorpus.mockResolvedValue({ rows: [] });
    listCaseBrowser.mockResolvedValue(THREE);
    const onSelectCase = vi.fn();
    const onToggleSelect = vi.fn();
    render(<ArtifactPane {...paneProps} tab="corpus" onSelectCase={onSelectCase} selectedIds={new Set()} onToggleSelect={onToggleSelect} runStatus="idle" runResult={null} runError={null} />);
    await screen.findByText("case_a");
    fireEvent.click(screen.getByTestId("case-check-zone-case_b")); // the label, not the input
    expect(onSelectCase).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("case-check-case_b")); // the input itself still toggles
    expect(onToggleSelect).toHaveBeenCalledWith("case_b");
    expect(onSelectCase).not.toHaveBeenCalled();
  });
});

// FINDING #2 (UI-pass 2026-07-04): the pane used to render the agent's DEFAULT case while the
// header said "No case selected" — two case states silently out of sync. The CaseTab now labels
// the fallback explicitly and offers the jump to the browser; a SELECTED case gets no notice.
describe("CaseTab — the default-case notice (displayed case ≠ armed case, finding #2)", () => {
  const KASE = {
    case_id: "default_case_01", transcript: "T", artifact: null, artifact_text: null,
    conditions: [], expected_safety_flags: [], injection_recipe: null, labeled: false,
  };

  it("a null caseId labels the shown case as the evaluation's default + Browse cases jumps to the Cases tab", async () => {
    getCase.mockResolvedValue(KASE);
    const setTab = vi.fn();
    render(<ArtifactPane {...paneProps} setTab={setTab} tab="case" activeCase={null} runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/no case is selected/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Browse cases/i }));
    expect(setTab).toHaveBeenCalledWith("corpus");
  });

  it("(non-vacuous) a SELECTED case renders with no default-case notice", async () => {
    getCase.mockResolvedValue({ ...KASE, case_id: "picked_case" });
    render(<ArtifactPane {...paneProps} tab="case" activeCase="picked_case" runStatus="idle" runResult={null} runError={null} />);
    expect(await screen.findByText(/picked_case/)).toBeInTheDocument();
    expect(screen.queryByText(/no case is selected/i)).toBeNull();
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
    expect(screen.getByText("Fabricated history")).toBeInTheDocument(); // the by-construction ground truth → flagLabel
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
    // the result + finding still render (label-free, real), flag relabeled via flagLabel
    expect(screen.getByText("Fabricated history")).toBeInTheDocument();
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
    expect(screen.getByText(/Automated fact-check failures/i)).toBeInTheDocument();
    // the flag (relabeled via flagLabel), contract type, and disposition all render
    const flagHits = screen.getAllByText("Silent degradation");
    expect(flagHits.length).toBeGreaterThan(0);
    expect(container.textContent).toContain("silent_degradation"); // contract_type (raw, unchanged)
    expect(container.textContent).toContain("inject_block"); // disposition (raw, unchanged)
  });

  it("does NOT render a Floor blocks section (no false BLOCK styling) when floor_adjustments is empty", () => {
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={NO_FLOOR_RUN} runError={null} />);
    expect(screen.queryByText(/Automated fact-check failures/i)).toBeNull();
  });
});

// REL-OPS-1 O2 — a terminology-subsumption suppression carries `terminology_edition` on its
// composite.grounded_adjustments entry (report.py). The Cleared-by-a-fact-check section renders it
// as muted secondary metadata; a legacy entry (pre-O2 run) renders exactly as before — no placeholder.
const EDITION_RUN = {
  case_id: "cv_mts_104",
  grade_path: "in_process",
  composite: {
    verdict: "approve",
    stage_verdict: "PASS",
    score: 0.0,
    active_findings: [],
    grounded_adjustments: [
      { flag: "FABRICATED_CLAIM", action: "suppress", contract: "repro/2",
        reason: "code-grounded by is-a subsumption via the connected terminology tool",
        terminology_edition: "SNOMED CT 2026-01-31" },
      { flag: "FABRICATED_HISTORY", action: "suppress", contract: "record-presence/v1",
        reason: "present in the patient record" },
    ],
    floor_adjustments: [],
  },
  calibration_check: { label_status: "unlabeled", status: "unlabeled", verdict_match_rate: null, ece: null, n_cases: 1, n_with_confidence: 0 },
};

describe("ReportTab — terminology edition on cleared entries (REL-OPS-1 O2)", () => {
  it("renders the edition on the entry that carries it; the legacy entry shows none", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={EDITION_RUN} runError={null} />,
    );
    expect(screen.getByText(/terminology edition: SNOMED CT 2026-01-31/)).toBeInTheDocument();
    // exactly ONE edition line — the record-presence entry carries no edition and no placeholder
    expect(container.textContent.match(/terminology edition/gi)).toHaveLength(1);
    expect(container.textContent).not.toContain("undefined");
  });
});

// META-VERDICT-1: the clinician's INDEPENDENT verdict + judge meta-audit (Clinical Scribe Review Layer-3).
describe("ReportTab — clinician verdict (META-VERDICT-1)", () => {
  const REPORT_RESULT = {
    case_id: "clinical_scribe_10",
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

describe("ReportTab error copy — calm + leak-free for a structured 500 (UX-COPY-ERR-1)", () => {
  it("a structured HTTP 500 shows a calm sentence WITHOUT the raw detail/verb/path/status or the 'unreachable/restart' line", () => {
    const err = 'POST /v1/run-eval → 500: {"detail":"no $0 replay baseline — run live or in_process"}';
    const { container } = render(<ArtifactPane {...paneProps} tab="report" runStatus="error" runError={err} />);
    expect(screen.getByText(/something went wrong on the server/i)).toBeInTheDocument(); // friendlyError 5xx line
    expect(container.textContent).not.toMatch(/POST \/v1|500|detail|no \$0 replay baseline/); // no raw leak
    expect(screen.queryByText(/unreachable|isn.t responding|restart it/i)).toBeNull(); // NOT claimed down (HTTP envelope present)
  });

  it("a genuine no-response (network) error DOES show the 'unreachable, restart' hint, calmly", () => {
    const { container } = render(<ArtifactPane {...paneProps} tab="report" runStatus="error" runError="Failed to fetch" />);
    expect(screen.getByText(/unreachable.*restart it/i)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Failed to fetch/); // raw network string never rendered
  });
});

describe("ReportTab — GRADE-GUARD-2: a no-baseline $0-replay failure → actionable guidance, not a raw 500", () => {
  // the VERBATIM error a baseline-less agent's $0 "Run eval" produces (walkthrough 2026-06-24): the
  // $0 replay has nothing to replay, so guide to Run live (which captures a baseline) instead of dumping
  // the 500. Distinct phrasing from the GRADE-GUARD-1 string above, so the two don't collide.
  const NO_BASELINE =
    "POST /v1/run-eval → 500: {\"detail\":\"grade subprocess failed (pack=healthcare): agent 'eval-1' " +
    "has no captured baseline — $0 replay is unavailable for imported/live-only cases; run it live or " +
    "in_process instead.\"}";

  it("renders 'No saved run to replay yet' + a Run-live next-step (no raw 'Run failed' / 500 dump)", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="error" runResult={null} runError={NO_BASELINE} />,
    );
    expect(screen.getByText(/No saved run to replay yet/i)).toBeInTheDocument();
    expect(container.textContent).toMatch(/Run live/);
    expect(screen.queryByText(/We couldn't finish that run/i)).toBeNull(); // not a raw failure dump
    expect(container.textContent).not.toMatch(/grade subprocess failed/); // the raw detail is hidden
  });

  it("(non-vacuous) a DIFFERENT error keeps the short validation reason (calm, no HTTP envelope)", () => {
    const other = 'POST /v1/run-eval → 422: {"detail":"malformed contract"}';
    const { container } = render(<ArtifactPane {...paneProps} tab="report" runStatus="error" runResult={null} runError={other} />);
    expect(screen.getByText(/We couldn't finish that run/i)).toBeInTheDocument();
    expect(screen.getByText(/malformed contract/i)).toBeInTheDocument(); // friendlyError KEEPS the short reason
    expect(container.textContent).not.toMatch(/POST \/v1|→ 422|detail/); // but drops the HTTP envelope / JSON
    expect(screen.queryByText(/No saved run to replay yet/i)).toBeNull();
  });
});

// REPLAY-HONESTY-1 (UI-pass 2026-07-04 finding #3): the BFF's replay refusals are PRECISE —
// a config-drift 409 ("the config changed since case X was last graded") is a DIFFERENT state
// from "no captured baseline", but both contain "run it live or in_process", so the old
// over-broad regex collapsed them into one generic "No saved run to replay yet" card. The
// drift 409 must render its own explanation (naming the case), and the no-baseline card must
// say when the real blocker is that no case is selected.
describe("ReportTab — REPLAY-HONESTY-1: config-drift 409 + no-case-selected get their own copy", () => {
  // the VERBATIM live 409 (validate stack, 2026-07-04) after a judge-config edit
  const DRIFT =
    "POST /v1/run-eval → 409: {\"detail\":\"agent 'repro_agent': the config changed since case " +
    "'cv_mts_001_clean_control' was last graded — re-grade (run it live or in_process) to see the " +
    "new verdict.\"}";
  const NO_BASELINE =
    "POST /v1/run-eval → 500: {\"detail\":\"grade subprocess failed (pack=healthcare): agent 'eval-1' " +
    "has no captured baseline — $0 replay is unavailable for imported/live-only cases; run it live or " +
    "in_process instead.\"}";

  it("a config-drift 409 renders the setup-changed card naming the case — NOT the no-baseline card", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="error" runResult={null} runError={DRIFT} />,
    );
    expect(screen.getByText(/setup changed since this case was last graded/i)).toBeInTheDocument();
    expect(container.textContent).toMatch(/cv_mts_001_clean_control/); // the server names the case — keep it
    expect(container.textContent).toMatch(/Run live/); // the actionable next step
    expect(screen.queryByText(/No saved run to replay yet/i)).toBeNull(); // the old collapse is gone
    expect(screen.queryByText(/We couldn't finish that run/i)).toBeNull(); // not a raw failure dump
    expect(container.textContent).not.toMatch(/POST \/v1|→ 409|detail/); // no HTTP envelope leak
  });

  it("no-baseline with NO case selected says the blocker is picking a case", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="error" runResult={null} runError={NO_BASELINE} />,
    );
    expect(screen.getByText(/No saved run to replay yet/i)).toBeInTheDocument();
    expect(container.textContent).toMatch(/No case is selected/i); // the distinct no-case state
    expect(container.textContent).toMatch(/Run live/);
  });

  it("no-baseline WITH a case selected names that case and skips the pick-a-case hint", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" activeCase="clinverdict_case09_pediatrics_adolescent_seizure"
        runStatus="error" runResult={null} runError={NO_BASELINE} />,
    );
    expect(screen.getByText(/No saved run to replay yet/i)).toBeInTheDocument();
    expect(container.textContent).toMatch(/clinverdict_case09_pediatrics_adolescent_seizure/);
    expect(container.textContent).not.toMatch(/No case is selected/i);
  });
});

// S-BS-168a — the Report's plain-English "What this means" summary. Mirrors live
// clinverdict_case01: an authored erasure_judge confidently rejects (BLOCK, 0.92) while
// the faithfulness reviewer is low-confidence uncertain (WARN, 0.32). The summary must
// name the verdict + a reason (A3) and be confidence-HONEST: the 0.32 needs-review must
// read as uncertain / a person should check, NOT as an equal confirmed issue (A4).
const CASE01_RUN = {
  case_id: "clinverdict_case01_neurology_hiv_patient",
  grade_path: "in_process",
  pipeline_run_id: "run-case01",
  composite: {
    verdict: "reject",
    stage_verdict: "BLOCK",
    score: 1,
    active_findings: ["INTENT_ERASURE", "HISTORY_OMISSION"],
    grounded_adjustments: [],
    floor_adjustments: [],
    case_outcome: "FLAGGED",
  },
  council: {
    case_outcome: "FLAGGED",
    votes: [
      { judge_role: "risk_judge", vote: "PASS", confidence: 1.0 },
      { judge_role: "policy_judge", vote: "PASS", confidence: 1.0 },
      { judge_role: "faithfulness_judge", vote: "WARN", confidence: 0.32, reason: "needs_review — HISTORY_OMISSION" },
      { judge_role: "erasure_judge", vote: "BLOCK", confidence: 0.92, reason: "reject — INTENT_ERASURE" },
    ],
  },
  calibration_check: { label_status: "unlabeled", n_cases: 1 },
};

describe("ReportTab — 'What this means' summary (S-BS-168a)", () => {
  it("A3 — renders a plain-English summary naming the verdict + a reason", () => {
    const { container } = render(
      <ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={CASE01_RUN} runError={null} />,
    );
    const summary = screen.getByTestId("report-summary");
    expect(screen.getByText(/what this means/i)).toBeInTheDocument();
    // names the verdict in plain words (the case was flagged) …
    expect(summary.textContent).toMatch(/flagged/i);
    // … and a reason — the reviewer that drove it.
    expect(summary.textContent).toMatch(/Erasure reviewer/);
    // recommends a human action.
    expect(summary.textContent).toMatch(/a person should|review this/i);
    expect(container).toBeTruthy();
  });

  it("A4 — confidence-honest: the 0.32 needs-review reads as uncertain, NOT a confirmed issue", () => {
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={CASE01_RUN} runError={null} />);
    const summary = screen.getByTestId("report-summary");
    const text = summary.textContent;
    // the low-confidence reviewer reads as uncertain / a person should check …
    expect(text).toMatch(/uncertain|unsure|a person should/i);
    expect(text).toMatch(/low confidence/i);
    // … and is NOT presented as a confirmed flag.
    expect(text).not.toMatch(/Faithfulness reviewer flagged/i);
    // the CONFIDENT reject is the one attributed as flagging (with high confidence).
    expect(text).toMatch(/Erasure reviewer flagged/i);
    expect(text).toMatch(/high confidence/i);
  });

  it("A4 — a clean PASS run reads as passed with no false 'flagged'/'uncertain' claim", () => {
    const passRun = {
      ...CASE01_RUN,
      composite: { ...CASE01_RUN.composite, verdict: "approve", stage_verdict: "PASS", score: 0, active_findings: [], case_outcome: "CLEAR" },
      council: {
        case_outcome: "CLEAR",
        votes: [
          { judge_role: "risk_judge", vote: "PASS", confidence: 1.0 },
          { judge_role: "policy_judge", vote: "PASS", confidence: 1.0 },
          { judge_role: "faithfulness_judge", vote: "PASS", confidence: 0.9 },
          { judge_role: "erasure_judge", vote: "PASS", confidence: 0.9 },
        ],
      },
    };
    render(<ArtifactPane {...paneProps} tab="report" runStatus="ready" runResult={passRun} runError={null} />);
    const text = screen.getByTestId("report-summary").textContent;
    expect(text).toMatch(/passed/i);
    expect(text).not.toMatch(/flagged|uncertain/i);
  });
});
