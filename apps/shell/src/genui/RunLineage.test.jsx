/* RunLineage.test.jsx — Theme C (C1): the shared run-lineage affordances. Extracted from the
   near-identical RunPanel.HistoryRow + AuditView.RunLineage. Guards the NEW pending state — the
   prior duplicated copies awaited with no feedback (a dead-click). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getRunHistory: vi.fn(),
  rehydrateRun: vi.fn(),
}));

import RunLineage from "./RunLineage.jsx";
import { getRunHistory, rehydrateRun } from "../bff.js";

beforeEach(() => {
  getRunHistory.mockReset();
  rehydrateRun.mockReset();
});

describe("RunLineage (shared lineage affordances)", () => {
  it("History shows a pending state while fetching, then lists prior versions", async () => {
    let resolve;
    getRunHistory.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<RunLineage runId="run-1234abcd" />);

    fireEvent.click(screen.getByRole("button", { name: /History/i }));
    // pending: the button reads "Loading…" and is disabled (the click registered)
    const hist = screen.getByRole("button", { name: /Loading…/i });
    expect(hist).toBeDisabled();
    expect(getRunHistory).toHaveBeenCalledWith("run-1234abcd");

    resolve({ history: [{ run_id: "v1aaaaaa", verdict: "PASS", grade_path: "replay" }] });
    expect(await screen.findByTestId("history-version")).toHaveTextContent("v1aaaaaa");
    // back to the idle label once settled
    expect(screen.getByRole("button", { name: /History/i })).toBeEnabled();
  });

  it("Rehydrate shows a pending state, then the reconstructed verdict", async () => {
    let resolve;
    rehydrateRun.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<RunLineage runId="run-1234abcd" />);

    fireEvent.click(screen.getByRole("button", { name: /Rehydrate/i }));
    expect(screen.getByRole("button", { name: /Rehydrating…/i })).toBeDisabled();

    resolve({ verdict: "BLOCK", run_id: "run-1234abcd" });
    expect(await screen.findByTestId("rehydrated-verdict")).toHaveTextContent("Flagged"); // BLOCK → verdictLabel
  });

  it("History reports an empty trail honestly", async () => {
    getRunHistory.mockResolvedValue({ history: [] });
    render(<RunLineage runId="run-1234abcd" />);
    fireEvent.click(screen.getByRole("button", { name: /History/i }));
    expect(await screen.findByText(/No prior versions/i)).toBeInTheDocument();
  });
});
