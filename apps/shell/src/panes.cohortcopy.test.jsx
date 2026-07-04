/* panes.cohortcopy.test.jsx — COHORT-SUBSET-1 last-mile: the cohort cost-confirm COPY must reflect
   the SUBSET the user picked. The bug (CONFIRMED): when "Run selected (N)" fires the grade-cohort
   bridge with detail.case_ids, confirmPaidRun correctly SCOPES gradeCases to that subset, but the
   CostModal title/body still read "Grade all cases (paid)?" / "grades every ingested case" — the
   copy LIES on a subset. The fix: a non-empty paid.caseIds → the title/body name the N-case subset;
   an absent/empty caseIds keeps today's "every ingested case" copy. Credit-safety unchanged (still
   confirm-gated). Drives the real window bridge → CenterPane → CostModal (bff.js mocked). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";

vi.mock("./bff.js", () => ({
  runEval: vi.fn().mockResolvedValue({ composite: { verdict: "approve" }, council: { votes: [] } }),
  gradeCases: vi.fn().mockResolvedValue({ summary: { grade_path: "in_process" }, scorecard: { cases: [], n_cases: 0, n_labeled: 0 } }),
  getConversation: vi.fn().mockResolvedValue({ agent: "ws0_default", thread: [] }),
  putConversation: vi.fn().mockResolvedValue({ ok: true }),
  deleteConversation: vi.fn().mockResolvedValue({ ok: true, removed: false }),
  hasStoredToken: vi.fn().mockReturnValue(false),
  logout: vi.fn(),
  signIn: vi.fn(),
  ingestPreview: vi.fn().mockResolvedValue({}),
  getRoleBindings: vi.fn().mockResolvedValue({ chat_ready: true, roles: {}, connected_providers: [] }),
  chatStream: vi.fn(async () => {}),
}));

import { CenterPane } from "./panes.jsx";
import { gradeCases } from "./bff.js";

beforeEach(() => { gradeCases.mockClear(); });

const dispatchCohort = (detail) =>
  act(() => { window.dispatchEvent(new CustomEvent("lithrim:grade-cohort", { detail })); });

const mount = () =>
  render(
    <CenterPane agent="ws0_default" activeCase={null} onActiveCase={vi.fn()}
      onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
  );

describe("CenterPane — COHORT-SUBSET-1: the cohort cost-confirm copy reflects the subset", () => {
  it("SUBSET: case_ids of length N → the copy names the N SELECTED cases (not 'every ingested case')", async () => {
    mount();
    dispatchCohort({ case_ids: ["a", "b", "c"] });
    const dialog = await screen.findByRole("dialog");
    // the subset headline is scoped to N and says "selected", NOT "all cases" / "every ingested case"
    expect(dialog.textContent).toMatch(/Grade 3 selected cases \(paid\)\?/i);
    expect(dialog.textContent).toMatch(/3 selected cases/i);
    expect(dialog.textContent).not.toMatch(/every ingested case/i);
    // credit-safety: opening the subset confirm spent NOTHING
    expect(gradeCases).not.toHaveBeenCalled();
    // and confirm still SCOPES the grade to that subset (the fix is copy-only; scoping is unchanged)
    fireEvent.click(screen.getByTestId("cost-confirm"));
    await waitFor(() => expect(gradeCases).toHaveBeenCalledTimes(1));
    expect(gradeCases).toHaveBeenCalledWith(expect.objectContaining({ case_ids: ["a", "b", "c"], in_process: true }));
  });

  it("ALL-CASES: no case_ids → today's 'every ingested case' copy is unchanged", async () => {
    mount();
    dispatchCohort({});
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toMatch(/Grade all cases \(paid\)\?/i);
    expect(dialog.textContent).toMatch(/every ingested case/i);
    // confirm grades the WHOLE cohort (no case_ids scoping)
    fireEvent.click(screen.getByTestId("cost-confirm"));
    await waitFor(() => expect(gradeCases).toHaveBeenCalledTimes(1));
    const arg = gradeCases.mock.calls[0][0];
    expect(arg.case_ids).toBeUndefined();
  });
});
