/* ScorecardCard.export.test.jsx — FT-FROM-SHELL-1: the export picks a format and says its split;
   training formats only from a calibration-split round. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ScorecardCard from "./ScorecardCard.jsx";

const per_task = [{ task: "OVERALL", n: 3, P: 50, R: 50, F1: 50, span_P: 50, span_R: 50, span_F1: 50, refused: 0 }];

describe("ScorecardCard export picker", () => {
  it("on a test-split round only the generic export is offered, and it says why", () => {
    render(<ScorecardCard cases={[]} per_task={per_task} round="after" split="test" job_id="job-t" onExport={vi.fn()} />);
    const sel = screen.getByTestId("export-format");
    expect(sel.querySelector('option[value="chat"]').disabled).toBe(true);
    expect(sel.querySelector('option[value="paper"]').disabled).toBe(true);
    expect(screen.getByTestId("export-split").textContent).toMatch(/from the test split · training formats need the calibration round/);
  });

  it("on a calibration round the azure-chat training file is sent as the chat format", async () => {
    const onExport = vi.fn().mockResolvedValue({ rows: 120, tiers: { "judge-only": 110, "floor-proved": 10 }, name: "export_calibration_calibration_job-c_chat.jsonl" });
    render(<ScorecardCard cases={[]} per_task={per_task} round="calibration" split="calibration" job_id="job-c" onExport={onExport} />);
    expect(screen.getByTestId("export-split").textContent).toMatch(/^from the calibration split$/);
    fireEvent.change(screen.getByTestId("export-format"), { target: { value: "chat" } });
    fireEvent.click(screen.getByTestId("export-corpus"));
    await waitFor(() => expect(onExport).toHaveBeenCalledWith("job-c", expect.objectContaining({ format: "chat", split: "calibration" })));
    expect((await screen.findByTestId("export-result")).textContent).toMatch(/120 rows written.*_chat\.jsonl/);
  });
});
