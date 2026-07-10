/* app.cohort.test.jsx — COHORT-SUBSET-1 (feat/cohort-and-subset-ui): the NON-chat "Grade all
   cases" cohort trigger. The ⌘K palette entry dispatches the lithrim:grade-cohort bridge that
   opens the SAME in-DOM cohort cost-confirm the chat's propose_run_all opens; the human's confirm
   is the sole paid path and grades the WHOLE cohort (POST /v1/cases/grade, no case_ids). This is
   the full real wiring — app.jsx palette action → window event → CenterPane bridge → CostModal →
   confirmPaidRun → gradeCases — over a fetch stub (same shape as app.costgate.test.jsx). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./app.jsx";

const gradeCalls = (fetchSpy) =>
  fetchSpy.mock.calls.filter(([url]) => String(url).includes("/v1/cases/grade"));

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url) => {
      const u = String(url);
      const body = u.includes("/v1/cases/grade")
        ? { matrix: [], summary: { grade_path: "in_process" }, scorecard: { cases: [], n_cases: 0, n_labeled: 0 } }
        : {};
      return Promise.resolve({ ok: true, json: async () => body });
    }),
  );
});

const openPalette = () => {
  // the global ⌘K keydown app.jsx installs on window
  fireEvent.keyDown(window, { key: "k", metaKey: true });
};

describe("COHORT-SUBSET-1: the ⌘K 'Grade all cases' cohort trigger", () => {
  it("opens the cohort cost-confirm and fires NO paid grade before the human confirms", async () => {
    render(<App mode="shell" setMode={() => {}} />);
    openPalette();
    fireEvent.click(await screen.findByText(/Grade all cases/i));
    // the SAME cohort modal the chat's propose_run_all opens
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toMatch(/Grade all cases \(paid\)\?/i);
    // credit-safety: the palette + bridge spent NOTHING — the confirm is the only paid path
    expect(gradeCalls(fetch)).toHaveLength(0);
  });

  it("confirming fires exactly one cohort grade — in_process, no case_ids (ALL cases)", async () => {
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    openPalette();
    fireEvent.click(await screen.findByText(/Grade all cases/i));
    fireEvent.click(await screen.findByRole("button", { name: /Grade all cases \(paid\)/i }));
    await waitFor(() => expect(gradeCalls(fetch)).toHaveLength(1));
    const [, init] = gradeCalls(fetch)[0];
    const sent = JSON.parse(String(init?.body || "{}"));
    expect(sent.in_process).toBe(true);
    expect(sent.case_ids).toBeUndefined(); // "Grade all" carries NO subset — the whole cohort
    unmount();
  });
});
