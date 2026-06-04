/* registry.test.jsx — A2: the tool-<name> registry renders each of the 9 config
   components from a typed tool-part, and an unknown tool degrades gracefully.
   (5 §5b widgets + UAP-1 agent_editor/audit_log + UAP-2 judge_editor + UAP-3 run_panel.) */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderTool, KNOWN_TOOLS } from "./index.js";

// FlagEditor reads GET /v1/ontology on mount; stub fetch so it doesn't reject.
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ severity_map: { block_at_or_above: 0.5, warn_above: 0, weights: { HIGH: 1, MEDIUM: 0.5, LOW: 0.2 } }, flags: [] }),
    }),
  );
});

const EXPECTED = {
  "tool-flag_editor": /Flags & severity|Loading ontology/i,
  "tool-contract_builder": /Verification contract/i,
  "tool-kb_picker": /Knowledge base/i,
  "tool-verdict_card": /Sample verdict/i,
  "tool-calibration_chart": /^Calibration$/, // anchored: the title, not the legend's "perfect calibration"
  "tool-agent_editor": /Loading agent|Agent ·/i, // UAP-1 R1 — config-plane write surface
  "tool-audit_log": /Audit trail/i, // UAP-1 R0 — the why/when/who/what view
  "tool-judge_editor": /Loading judge|Judge ·/i, // UAP-2 R2 — ontology-assignment authoring
  "tool-run_panel": /Run evaluation/i, // UAP-3 R4 — the processing surface
};

describe("renderTool registry", () => {
  it("knows all 9 config tools", () => {
    expect(KNOWN_TOOLS).toHaveLength(9);
    expect(new Set(KNOWN_TOOLS)).toEqual(new Set(Object.keys(EXPECTED)));
  });

  for (const tool of Object.keys(EXPECTED)) {
    it(`renders ${tool} from an output-available part (not the fallback)`, () => {
      render(<div>{renderTool({ type: tool, state: "output-available" })}</div>);
      expect(screen.getByText(EXPECTED[tool])).toBeInTheDocument();
      expect(screen.queryByText(/Unsupported component/i)).not.toBeInTheDocument();
    });
  }

  it("degrades gracefully on an unknown tool", () => {
    render(<div>{renderTool({ type: "tool-does_not_exist", state: "output-available" })}</div>);
    expect(screen.getByText(/Unsupported component/i)).toBeInTheDocument();
  });

  it("falls back on a missing/typeless part", () => {
    render(<div>{renderTool(null)}</div>);
    expect(screen.getByText(/Unsupported component/i)).toBeInTheDocument();
  });

  it("shows an error note on output-error", () => {
    render(<div>{renderTool({ type: "tool-verdict_card", state: "output-error", errorText: "boom" })}</div>);
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it("shows a placeholder while input is streaming", () => {
    render(<div>{renderTool({ type: "tool-kb_picker", state: "input-streaming" })}</div>);
    expect(screen.getByText(/Preparing tool-kb_picker/i)).toBeInTheDocument();
  });

  // S-BS-19 / Ambiguity-2: the LOCKED datapoint prop convention is flat-spread
  // (part.output fields are direct props, no {data} wrapper). Both datapoint cards conform.
  it("renders VerdictCard from flat-spread part.output (locked convention)", () => {
    render(<div>{renderTool({ type: "tool-verdict_card", state: "output-available", output: { verdict: "FAIL", confidence: "0.10" } })}</div>);
    expect(screen.getByText("FAIL")).toBeInTheDocument(); // flat field, not output.data.verdict
    expect(screen.getByText("0.10")).toBeInTheDocument();
  });

  it("renders CalibrationChart from flat-spread part.output (locked convention)", () => {
    render(<div>{renderTool({ type: "tool-calibration_chart", state: "output-available", output: { ece: "9.9%", brier: "0.500" } })}</div>);
    expect(screen.getByText("9.9%")).toBeInTheDocument();
    expect(screen.getByText("0.500")).toBeInTheDocument();
  });
});
