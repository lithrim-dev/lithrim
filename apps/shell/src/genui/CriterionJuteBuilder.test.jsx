/* CriterionJuteBuilder.test.jsx — CRITERION-JUTE-1d: the inline card that ties the stack
   together. An SME picks a tool+call, a plain-English criterion seeds generation, "Generate + gate"
   runs the corpus gate ($0 preview), the GateReport renders inline, and "Pin" writes the mcp_call +
   arguments_jute contract — DISABLED until the gate passes. Mirrors ContractBuilder.test.jsx (mock
   bff, render, fireEvent).

   Covers:
     A1 — renders (tool picker from listTools, the criterion seed).
     A2 — a PASSING gate (Generate) enables Pin + shows 22/22 · 24/24.
     A3 — a FAILING gate shows failures[] and keeps Pin DISABLED.
     A4 — onResult fires ONLY on a successful Pin (the human's Pin is the write). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// the card lists tools on mount (listTools) and runs the endpoint on Generate/Pin
// (generateCriterionJute). Mock both so mounting never reaches a real fetch.
vi.mock("../bff.js", () => ({
  listTools: vi.fn().mockResolvedValue({
    declared: [{ id: "gate_snomed_subsumption" }, { id: "hermes_snomed" }],
    authored: [],
  }),
  generateCriterionJute: vi.fn(),
}));

import CriterionJuteBuilder from "./CriterionJuteBuilder.jsx";
import { listTools, generateCriterionJute } from "../bff.js";

const PASS_REPORT = {
  status: "preview",
  arguments_jute: "concept_id: $ num(codes.record_snomed)\n",
  arguments_jute_sha256: "abc123",
  gate_report: {
    negatives_cleared: 22, negatives_total: 22,
    positives_standing: 24, positives_total: 24,
    span_bind_ok: 2, span_bind_cases: 2,
    failures: [], passed: true,
  },
};

const FAIL_REPORT = {
  status: "preview",
  arguments_jute: "concept_id: $ num(codes.note_snomed)\n",
  arguments_jute_sha256: "def456",
  gate_report: {
    negatives_cleared: 0, negatives_total: 22,
    positives_standing: 2, positives_total: 24,
    span_bind_ok: 0, span_bind_cases: 2,
    failures: ["cv_mts_010", "cv_mts_011"], passed: false,
  },
};

beforeEach(() => {
  listTools.mockClear();
  generateCriterionJute.mockClear();
});

describe("CriterionJuteBuilder — A1 renders + seeds", () => {
  it("renders the tool picker (from listTools) and the seeded criterion", async () => {
    render(
      <CriterionJuteBuilder
        agent="cjute1d"
        flag_code="UPCODING_RISK"
        criterion="record-vs-note subsumption"
        onResult={vi.fn()}
      />,
    );
    await waitFor(() => expect(listTools).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText("criterion")).toHaveValue("record-vs-note subsumption");
    // Pin is disabled before any gate runs.
    expect(screen.getByRole("button", { name: /^Pin/i })).toBeDisabled();
  });
});

describe("CriterionJuteBuilder — A2 a passing gate enables Pin", () => {
  it("runs the preview gate on Generate, shows 22/22 · 24/24, and ENABLES Pin", async () => {
    generateCriterionJute.mockResolvedValueOnce(PASS_REPORT);
    render(
      <CriterionJuteBuilder agent="cjute1d" flag_code="UPCODING_RISK" tool="gate_snomed_subsumption" call="subsumed_by" criterion="c" onResult={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate \+ gate/i }));

    await waitFor(() => expect(generateCriterionJute).toHaveBeenCalledTimes(1));
    // the preview call is commit:false ($0, no write).
    expect(generateCriterionJute.mock.calls[0][0].commit).toBe(false);
    // the gate report renders inline.
    expect(await screen.findByText(/22\s*\/\s*22/)).toBeInTheDocument();
    expect(screen.getByText(/24\s*\/\s*24/)).toBeInTheDocument();
    // a passing gate ENABLES Pin.
    await waitFor(() => expect(screen.getByRole("button", { name: /^Pin/i })).not.toBeDisabled());
  });
});

describe("CriterionJuteBuilder — A3 a failing gate keeps Pin disabled", () => {
  it("shows the failing case_ids and keeps Pin DISABLED", async () => {
    generateCriterionJute.mockResolvedValueOnce(FAIL_REPORT);
    render(
      <CriterionJuteBuilder agent="cjute1d" flag_code="UPCODING_RISK" tool="gate_snomed_subsumption" call="subsumed_by" criterion="c" onResult={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate \+ gate/i }));

    await waitFor(() => expect(generateCriterionJute).toHaveBeenCalledTimes(1));
    // the failing case ids surface inline.
    expect(await screen.findByText(/cv_mts_010/)).toBeInTheDocument();
    // a failing gate keeps Pin DISABLED (the human can't pin a contract that fails the gate).
    expect(screen.getByRole("button", { name: /^Pin/i })).toBeDisabled();
  });
});

describe("CriterionJuteBuilder — A4 onResult fires only on a successful Pin", () => {
  it("fires onResult on a successful pin (commit:true), not on the preview", async () => {
    const onResult = vi.fn();
    generateCriterionJute
      .mockResolvedValueOnce(PASS_REPORT) // Generate (preview)
      .mockResolvedValueOnce({ status: "pinned", contract: { flag_code: "UPCODING_RISK" }, gate_report: PASS_REPORT.gate_report }); // Pin (commit)
    render(
      <CriterionJuteBuilder agent="cjute1d" flag_code="UPCODING_RISK" tool="gate_snomed_subsumption" call="subsumed_by" criterion="c" onResult={onResult} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate \+ gate/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^Pin/i })).not.toBeDisabled());
    // the preview did NOT fire onResult (only the Pin does).
    expect(onResult).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /^Pin/i }));
    await waitFor(() => expect(generateCriterionJute).toHaveBeenCalledTimes(2));
    expect(generateCriterionJute.mock.calls[1][0].commit).toBe(true);
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
  });
});
