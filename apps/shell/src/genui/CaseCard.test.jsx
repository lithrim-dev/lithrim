/* CaseCard.test.jsx — CHATBIND-3: the inline Case Summary card self-fetches GET /v1/case and
   its "View case" opens the full Case tab. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("../bff.js", () => ({ getCase: vi.fn() }));

import CaseCard from "./CaseCard.jsx";
import { getCase } from "../bff.js";

beforeEach(() => getCase.mockReset());

describe("CaseCard — inline source-case summary", () => {
  it("self-fetches the case, renders the summary, and 'View case' opens the Case tab", async () => {
    getCase.mockResolvedValue({
      case_id: "bench_scribe_v1_inject_condition",
      transcript: "Dr: Hello. Patient: I'm here for a sprain.",
      artifact_text: "SUBJECTIVE: 28M presents for sprain. PMH: diabetes.",
      expected_safety_flags: ["FABRICATED_HISTORY"],
    });
    const onOpenArtifact = vi.fn();
    render(<CaseCard agent="ws0_default" onOpenArtifact={onOpenArtifact} />);
    expect(getCase).toHaveBeenCalledWith("ws0_default"); // self-fetches the active agent
    expect(await screen.findByText("Source case")).toBeInTheDocument();
    expect(screen.getByText("bench_scribe_v1_inject_condition")).toBeInTheDocument();
    expect(screen.getByText("FABRICATED_HISTORY")).toBeInTheDocument(); // the planted defect
    expect(screen.getByText(/SUBJECTIVE: 28M presents/)).toBeInTheDocument(); // the note snippet
    // NON-VACUOUS: clicking "View case" drives onOpenArtifact("case")
    fireEvent.click(screen.getByText(/View case/));
    expect(onOpenArtifact).toHaveBeenCalledWith("case");
  });

  it("labels a clean-negative case 'clean' (nothing planted)", async () => {
    getCase.mockResolvedValue({
      case_id: "imported_scheduling_clean",
      transcript: "Patient books a follow-up.",
      artifact_text: "",
      expected_safety_flags: [],
    });
    render(<CaseCard agent="imported_scheduling_clean" onOpenArtifact={() => {}} />);
    expect(await screen.findByText("clean")).toBeInTheDocument();
  });
});
