/* bff.test.jsx — A6 / S-BS-18: the React↔BFF binding. Mocks fetch, drives the
   bff.js client (POST /v1/run-eval), and asserts the real-composite shape renders
   through artifact.jsx ReportTab (via the exported ArtifactPane). Guards the React
   side that the Python tests/test_ws5_bff.py round-trip does not cover. */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { runEval, getOntology } from "./bff.js";
import { ArtifactPane } from "./artifact.jsx";

// A representative /v1/run-eval response: the S-BS-7 clinical story (reject; one
// active FABRICATED_HISTORY finding; the MED FP grounded-suppressed by the contract).
const COMPOSITE_RESPONSE = {
  case_id: "bench_scribe_v1_inject_condition_1bd0f10dc7b5",
  grade_path: "replay",
  composite: {
    verdict: "reject",
    stage_verdict: "BLOCK",
    score: 1.0,
    active_findings: ["FABRICATED_HISTORY"],
    grounded_adjustments: [
      { flag: "MEDICATION_NOT_IN_TRANSCRIPT", action: "suppress", contract: "med-presence-check/v1", reason: "zidovudine is verbatim in the transcript" },
    ],
  },
  calibration_check: { n_cases: 1, verdict_match_rate: "1/1", status: "PASS", ece: 0.5, caveat: "N=1 diagnostic only" },
};

function mockFetch(body, ok = true) {
  return vi.fn().mockResolvedValue({ ok, status: ok ? 200 : 500, json: async () => body, text: async () => JSON.stringify(body) });
}

const paneProps = { width: 440, full: false, tab: "report", setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

describe("bff.js → ReportTab binding (S-BS-18)", () => {
  it("runEval() POSTs /v1/run-eval and parses the composite", async () => {
    vi.stubGlobal("fetch", mockFetch(COMPOSITE_RESPONSE));
    const result = await runEval({ live: false });

    expect(fetch).toHaveBeenCalledWith(
      "/v1/run-eval",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ agent: "ws0_default", live: false }) }),
    );
    expect(result.composite.verdict).toBe("reject");
    expect(result.composite.active_findings).toContain("FABRICATED_HISTORY");
  });

  it("renders the real composite through ReportTab", async () => {
    vi.stubGlobal("fetch", mockFetch(COMPOSITE_RESPONSE));
    const result = await runEval({ live: false });

    render(<ArtifactPane {...paneProps} runStatus="ready" runResult={result} runError={null} />);

    expect(screen.getByText(/Blocked by quality gate/i)).toBeInTheDocument(); // reject banner
    expect(screen.getByText("FABRICATED_HISTORY")).toBeInTheDocument(); // active finding
    expect(screen.getByText("MEDICATION_NOT_IN_TRANSCRIPT")).toBeInTheDocument(); // grounded suppression
    expect(screen.getByText(/1\/1 · PASS/)).toBeInTheDocument(); // calibration_check
  });

  it("surfaces an error when the BFF call fails", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "down" }, false));
    await expect(runEval({ live: false })).rejects.toThrow(/run-eval/);
  });

  it("getOntology() hits GET /v1/ontology (read-only)", async () => {
    vi.stubGlobal("fetch", mockFetch({ domain: "clinical", flags: [] }));
    const ont = await getOntology("ws0_default");
    expect(fetch).toHaveBeenCalledWith("/v1/ontology?agent=ws0_default", expect.anything());
    expect(ont.domain).toBe("clinical");
  });
});
