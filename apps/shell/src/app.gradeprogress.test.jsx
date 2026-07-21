/* app.gradeprogress.test.jsx — GRADE-PROGRESS-1: the StatusBar batch-grade chip. The cohort
   grade is one POST that runs for minutes with no chrome-level indication once the CostModal
   settles; the chip in the PERSISTENT bottom status bar shows "grading …" while the batch is in
   flight and disappears on completion (success OR error). Full real wiring over a deferred fetch
   stub (same shape as app.cohort.test.jsx): palette/bridge → CostModal → confirmPaidRun →
   gradeCases → the module progress store → the StatusBar chip. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./app.jsx";
import { endBatch } from "./progress.js";

let grade; // { resolve, reject } for the pending /v1/cases/grade call
beforeEach(() => {
  endBatch();
  grade = null;
  vi.stubGlobal(
    "fetch",
    vi.fn((url) => {
      const u = String(url);
      if (u.includes("/v1/cases/grade"))
        return new Promise((resolve, reject) => {
          grade = {
            resolve: () =>
              resolve({ ok: true, json: async () => ({ matrix: [], summary: { grade_path: "in_process" }, scorecard: { cases: [], n_cases: 0, n_labeled: 0 } }) }),
            reject: () => reject(new Error("boom")),
          };
        });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }),
  );
});

const openPalette = () => fireEvent.keyDown(window, { key: "k", metaKey: true });

describe("GRADE-PROGRESS-1: the StatusBar batch-grade chip", () => {
  it("grade-all: the chip appears while the batch POST is in flight and disappears on completion", async () => {
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    expect(screen.queryByTestId("grade-progress")).toBeNull();
    openPalette();
    fireEvent.click(await screen.findByText(/Grade all cases — one paid cohort batch/i));
    fireEvent.click(await screen.findByRole("button", { name: /Grade all cases \(paid\)/i }));
    const chip = await screen.findByTestId("grade-progress");
    expect(chip.textContent).toMatch(/grading…/);
    grade.resolve();
    await waitFor(() => expect(screen.queryByTestId("grade-progress")).toBeNull());
    unmount();
  });

  it("Run selected subset: the chip carries the case count and survives artifact chrome changes", async () => {
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    // the SAME bridge the Cases-browser "Run selected (N)" button dispatches
    fireEvent(window, new CustomEvent("lithrim:grade-cohort", { detail: { case_ids: ["a", "b", "c"] } }));
    fireEvent.click(await screen.findByRole("button", { name: /Grade 3 selected cases \(paid\)/i }));
    const chip = await screen.findByTestId("grade-progress");
    expect(chip.textContent).toMatch(/grading 3 cases…/);
    // chrome churn while the batch is still in flight: open the artifact pane (Explore case)
    openPalette();
    fireEvent.click(await screen.findByTestId("cmdk-item-explore-case"));
    expect(screen.getByTestId("grade-progress").textContent).toMatch(/grading 3 cases…/);
    grade.resolve();
    await waitFor(() => expect(screen.queryByTestId("grade-progress")).toBeNull());
    unmount();
  });

  it("a failed batch clears the chip (no stuck 'grading…')", async () => {
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    fireEvent(window, new CustomEvent("lithrim:grade-cohort", { detail: {} }));
    fireEvent.click(await screen.findByRole("button", { name: /Grade all cases \(paid\)/i }));
    await screen.findByTestId("grade-progress");
    grade.reject();
    await waitFor(() => expect(screen.queryByTestId("grade-progress")).toBeNull());
    unmount();
  });
});
