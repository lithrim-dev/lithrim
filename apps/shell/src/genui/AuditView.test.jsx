/* AuditView.test.jsx — RUNTRAIL-8 A3: the run-provenance report surfaces the lineage
   (grade_path tag + the replay_of baseline) beside the verdict. Mocks bff.js (no live
   BFF), reusing the vi.fn() pattern from RunPanel.test.jsx / artifact.test.jsx. */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getAudit: vi.fn().mockResolvedValue({ records: [] }),
  getRuns: vi.fn().mockResolvedValue({
    runs: [
      // LAYER0/2 read surface: the floor's outcome rides the row (council BLOCK → floor PASS)
      { run_id: "a57bd49d-aaaa", case_id: "snomed_inj_13_gpa", verdict: "BLOCK", grade_path: "in_process", replay_of: null, agent: "eval-1", ts: "2026-06-30T17:53:50Z", grounded_verdict: "PASS", floor_suppressed: 2 },
      { run_id: "c0ffee00-cccc", case_id: "snomed_inj_13_gpa", verdict: "PASS", grade_path: "replay", replay_of: "a57bd49d-aaaa", agent: "eval-1", ts: "2026-06-30T17:50:00Z", grounded_verdict: null, floor_suppressed: null },
      { run_id: "d00d1234-dddd", case_id: "case-10", verdict: "PASS", grade_path: "live", replay_of: null, agent: "eval-1", ts: "2026-06-30T17:40:00Z" },
    ],
  }),
  getRunAudit: vi.fn().mockResolvedValue({
    verdict: "BLOCK",
    actor: { id: "ws0_default" },
    grade_path: "replay",
    replay_of: "b1c2d3e4-bbbb-0000-0000-000000000000",
    judges: [{ judge_role: "risk_judge", vote: "BLOCK", reasoning: "WRONG_DOSAGE" }],
    grounded_verdict: "PASS",
    grounded: {
      verdict: "PASS", original_verdict: "WARN",
      active: [],
      suppressed: [{
        code: "FABRICATED_CLAIM", contract: "snomed-subsumption/v1", disproved: true,
        reason: "every documented history item is grounded in the patient record by SNOMED subsumption",
      }],
    },
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
import { getAudit, getRuns, getRunAudit, getRunHistory, rehydrateRun } from "../bff.js";

beforeEach(() => {
  getAudit.mockClear();
  getRuns.mockClear();
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

describe("AuditView (tool-audit_log) — RUNTRAIL-11 the trail, grouped by case", () => {
  it("R11a — getRuns drives a per-case run list (no run id typed)", async () => {
    render(<AuditView />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());

    const trail = await screen.findByTestId("run-trail");
    // grouped by case_id: the two snomed runs sit under one header, case-10 under its own
    const groups = within(trail).getAllByTestId("trail-case");
    expect(groups).toHaveLength(2);
    expect(groups[0]).toHaveTextContent("snomed_inj_13_gpa");
    expect(within(trail).getAllByTestId("trail-run")).toHaveLength(3);
    // a row carries the headline lineage: verdict + grade_path tag + the replay baseline
    const rows = within(trail).getAllByTestId("trail-run");
    expect(rows[1]).toHaveTextContent(/replays/i); // the replay row links its baseline
  });

  it("R11b — clicking a trail row loads that run's provenance (no typing)", async () => {
    render(<AuditView />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());
    const trail = await screen.findByTestId("run-trail");

    fireEvent.click(within(trail).getAllByTestId("trail-run")[0]);
    await waitFor(() => expect(getRunAudit).toHaveBeenCalledWith("a57bd49d-aaaa"));
    expect(await screen.findByTestId("run-report")).toBeTruthy();
  });
});

/* RUN-TRAIL-CASE-SCOPE — given caseId (threaded from the review_runs audit card), the
   trail fetch is scoped to that case and its group renders alone, with an explicit
   see-the-full-trail affordance one click away. Without caseId: identical to today. */
describe("AuditView — RUN-TRAIL-CASE-SCOPE: the trail scopes to the card's case", () => {
  const ALL_ROWS = [
    { run_id: "a57bd49d-aaaa", case_id: "snomed_inj_13_gpa", verdict: "BLOCK", grade_path: "in_process", replay_of: null, agent: "eval-1", ts: "2026-06-30T17:53:50Z" },
    { run_id: "d00d1234-dddd", case_id: "case-10", verdict: "PASS", grade_path: "live", replay_of: null, agent: "eval-1", ts: "2026-06-30T17:40:00Z" },
  ];
  const SCOPED_ROWS = [ALL_ROWS[0]];
  const scopeAware = (limit, opts = {}) =>
    Promise.resolve({ runs: opts.caseId ? SCOPED_ROWS.filter((r) => r.case_id === opts.caseId) : ALL_ROWS });

  afterEach(() => {
    // restore the module-level default impl (mockImplementation would otherwise leak
    // into the FLOOR-VIS-1 tests below, which rely on the 3-row fixture)
    getRuns.mockResolvedValue({
      runs: [
        { run_id: "a57bd49d-aaaa", case_id: "snomed_inj_13_gpa", verdict: "BLOCK", grade_path: "in_process", replay_of: null, agent: "eval-1", ts: "2026-06-30T17:53:50Z", grounded_verdict: "PASS", floor_suppressed: 2 },
        { run_id: "c0ffee00-cccc", case_id: "snomed_inj_13_gpa", verdict: "PASS", grade_path: "replay", replay_of: "a57bd49d-aaaa", agent: "eval-1", ts: "2026-06-30T17:50:00Z", grounded_verdict: null, floor_suppressed: null },
        { run_id: "d00d1234-dddd", case_id: "case-10", verdict: "PASS", grade_path: "live", replay_of: null, agent: "eval-1", ts: "2026-06-30T17:40:00Z" },
      ],
    });
  });

  it("S1 — caseId prop scopes the fetch; only that case's group renders, with the see-all affordance", async () => {
    getRuns.mockImplementation(scopeAware);
    render(<AuditView caseId="snomed_inj_13_gpa" />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());
    expect(getRuns.mock.calls[0][1]).toMatchObject({ caseId: "snomed_inj_13_gpa" });

    const trail = await screen.findByTestId("run-trail");
    const groups = within(trail).getAllByTestId("trail-case");
    expect(groups).toHaveLength(1);
    expect(groups[0]).toHaveTextContent("snomed_inj_13_gpa");
    expect(screen.getByRole("button", { name: /see all runs/i })).toBeTruthy();
  });

  it("S2 — the see-all affordance is one click away: it refetches unscoped and renders every group", async () => {
    getRuns.mockImplementation(scopeAware);
    render(<AuditView caseId="snomed_inj_13_gpa" />);
    await screen.findByTestId("run-trail");

    fireEvent.click(screen.getByRole("button", { name: /see all runs/i }));
    await waitFor(() => {
      const last = getRuns.mock.calls[getRuns.mock.calls.length - 1];
      expect((last[1] || {}).caseId).toBeFalsy();
    });
    await waitFor(() => expect(within(screen.getByTestId("run-trail")).getAllByTestId("trail-case")).toHaveLength(2));
  });

  it("S3 — without caseId the fetch is unscoped and behavior is identical to today", async () => {
    getRuns.mockImplementation(scopeAware);
    render(<AuditView />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());
    expect((getRuns.mock.calls[0][1] || {}).caseId).toBeFalsy();
    const trail = await screen.findByTestId("run-trail");
    expect(within(trail).getAllByTestId("trail-case")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /see all runs/i })).toBeNull();
  });

  it("S4 — replay rows carry the explicit replay label; authoritative rows say so (no re-sort)", async () => {
    getRuns.mockImplementation(() => Promise.resolve({
      runs: [
        // the replay row copies its source run's ts (older than the row below it) — the
        // list stays insertion-ordered; the LABEL is what disambiguates, not a re-sort.
        { run_id: "c0ffee00-cccc", case_id: "snomed_inj_13_gpa", verdict: "PASS", grade_path: "replay", replay_of: "a57bd49d-aaaa", agent: "eval-1", ts: "2026-06-30T17:00:00Z" },
        { run_id: "a57bd49d-aaaa", case_id: "snomed_inj_13_gpa", verdict: "BLOCK", grade_path: "in_process", replay_of: null, agent: "eval-1", ts: "2026-06-30T17:53:50Z" },
      ],
    }));
    render(<AuditView />);
    const trail = await screen.findByTestId("run-trail");
    const rows = within(trail).getAllByTestId("trail-run");
    expect(rows[0]).toHaveTextContent(/replays a57bd49d/i); // the explicit replay label
    expect(rows[1]).toHaveTextContent(/authoritative/i);
  });
});

describe("AuditView — FLOOR-VIS-1: the grounding floor's outcome is visible", () => {
  it("F1 — a trail row with a floor outcome shows the floor chip; legacy rows show none", async () => {
    render(<AuditView />);
    await waitFor(() => expect(getRuns).toHaveBeenCalled());
    const trail = await screen.findByTestId("run-trail");
    const rows = within(trail).getAllByTestId("trail-run");
    // row 0: council BLOCK, floor PASS with 2 suppressions → the chip carries both
    expect(rows[0]).toHaveTextContent(/floor/i);
    expect(within(rows[0]).getByTestId("floor-chip")).toHaveTextContent("Passed");
    expect(within(rows[0]).getByTestId("floor-chip")).toHaveTextContent("2 suppressed");
    // rows 1+2: legacy blobs (no grounded projection) → NO floor chip, nothing fabricated
    expect(within(rows[1]).queryByTestId("floor-chip")).toBeNull();
    expect(within(rows[2]).queryByTestId("floor-chip")).toBeNull();
  });

  it("F2 — the run report renders the grounded section: verdict flip + each suppression with its contract + reason", async () => {
    render(<AuditView runId="a57bd49d-aaaa" />);
    await waitFor(() => expect(getAudit).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Load run/i }));
    await screen.findByTestId("run-report");

    const grounded = await screen.findByTestId("run-grounded");
    expect(grounded).toHaveTextContent(/grounding floor/i);
    // the flip: council WARN → floor PASS
    expect(grounded).toHaveTextContent("Needs a look");
    expect(grounded).toHaveTextContent("Passed");
    // the suppression line: flag + the deterministic contract that disproved it + the why
    expect(grounded).toHaveTextContent(/fabricated claim/i);
    expect(grounded).toHaveTextContent("snomed-subsumption/v1");
    expect(grounded).toHaveTextContent(/grounded in the patient record/i);
  });

  // REL-OPS-1 O2: a terminology-grounded suppression carries the release that decided it.
  it("F4 — a suppression carrying terminology_edition renders it as muted metadata", async () => {
    getRunAudit.mockResolvedValueOnce({
      verdict: "BLOCK", actor: { id: "ws0_default" }, grade_path: "in_process", judges: [],
      grounded_verdict: "PASS",
      grounded: {
        verdict: "PASS", original_verdict: "WARN", active: [],
        suppressed: [{
          code: "FABRICATED_CLAIM", contract: "repro/2", disproved: true,
          reason: "code-grounded by is-a subsumption via the connected terminology tool",
          terminology_edition: "unrecorded",
        }],
      },
    });
    render(<AuditView runId="a57bd49d-aaaa" />);
    await waitFor(() => expect(getAudit).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Load run/i }));
    const grounded = await screen.findByTestId("run-grounded");
    expect(grounded).toHaveTextContent(/terminology edition: unrecorded/);
  });

  it("F5 — a legacy suppression (no edition field) renders NO edition text (no placeholder)", async () => {
    render(<AuditView runId="a57bd49d-aaaa" />);
    await waitFor(() => expect(getAudit).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Load run/i }));
    const grounded = await screen.findByTestId("run-grounded");
    expect(grounded.textContent).not.toMatch(/terminology edition/i);
    expect(grounded.textContent).not.toMatch(/undefined/);
  });

  it("F3 — a legacy run report (no grounded block) renders no floor section", async () => {
    getRunAudit.mockResolvedValueOnce({
      verdict: "BLOCK", actor: { id: "ws0_default" }, grade_path: "replay",
      judges: [], grounded: null, grounded_verdict: null,
    });
    render(<AuditView runId="c0ffee00-cccc" />);
    await waitFor(() => expect(getAudit).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Load run/i }));
    await screen.findByTestId("run-report");
    expect(screen.queryByTestId("run-grounded")).toBeNull();
  });
});
