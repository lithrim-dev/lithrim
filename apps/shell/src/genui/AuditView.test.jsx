/* AuditView.test.jsx — RUNTRAIL-8 A3: the run-provenance report surfaces the lineage
   (grade_path tag + the replay_of baseline) beside the verdict. Mocks bff.js (no live
   BFF), reusing the vi.fn() pattern from RunPanel.test.jsx / artifact.test.jsx. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getAudit: vi.fn().mockResolvedValue({ records: [] }),
  getRunAudit: vi.fn().mockResolvedValue({
    verdict: "BLOCK",
    actor: { id: "ws0_default" },
    grade_path: "replay",
    replay_of: "b1c2d3e4-bbbb-0000-0000-000000000000",
    judges: [{ judge_role: "risk_judge", vote: "BLOCK", reasoning: "WRONG_DOSAGE" }],
  }),
}));

import AuditView from "./AuditView.jsx";
import { getAudit, getRunAudit } from "../bff.js";

beforeEach(() => {
  getAudit.mockClear();
  getRunAudit.mockClear();
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
});
