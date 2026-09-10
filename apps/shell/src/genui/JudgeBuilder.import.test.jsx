/* JudgeBuilder.import.test.jsx — UI-JOURNEY-1 (B10): prefill a new reviewer from a definition file. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getOntology: vi.fn().mockResolvedValue({ flags: [{ flag: "SOURCE_CONTRADICTION" }, { flag: "UNSUPPORTED_ASSERTION" }] }),
  listModels: vi.fn().mockResolvedValue({ models: [] }),
  createJudge: vi.fn().mockResolvedValue({ status: "ok", audit_id: "a1" }),
}));

import JudgeBuilder from "./JudgeBuilder.jsx";

const DEF = { role: "ragtruth_detector", lens_codes: ["SOURCE_CONTRADICTION", "UNSUPPORTED_ASSERTION"], owned_codes: [], role_prompt: "YOU ARE THE DETECTOR." };

describe("JudgeBuilder — load a definition", () => {
  it("prefills role, lens, owned codes and prompt from the file; nothing is written", async () => {
    render(<JudgeBuilder agent="ws0_default" onResult={vi.fn()} />);
    fireEvent.change(screen.getByTestId("judge-import"), { target: { files: [new File([JSON.stringify(DEF)], "judge.ragtruth_detector.json")] } });
    const note = await screen.findByTestId("judge-import-note");
    expect(note.textContent).toMatch(/role ragtruth_detector, 2 lens codes, prompt 21 chars/);
    await waitFor(() => expect(screen.getByLabelText("reviewer id")).toHaveValue("ragtruth_detector"));
    const { createJudge } = await import("../bff.js");
    expect(createJudge).not.toHaveBeenCalled();
  });

  it("a file with no role is refused with the reason", async () => {
    render(<JudgeBuilder agent="ws0_default" onResult={vi.fn()} />);
    fireEvent.change(screen.getByTestId("judge-import"), { target: { files: [new File(["{}"], "x.json")] } });
    expect((await screen.findByTestId("judge-import-note")).textContent).toMatch(/carries no role/);
  });
});
