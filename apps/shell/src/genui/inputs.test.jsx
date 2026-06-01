/* inputs.test.jsx — A3: FlagEditor / ContractBuilder / KbPicker collect input and
   return a result object via onResult(). FlagEditor reads the ontology via GET only
   (mocked here) — no PUT this phase. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// FlagEditor reads GET /v1/ontology via bff.getOntology — mock it (read-only).
vi.mock("../bff.js", () => ({
  getOntology: vi.fn().mockResolvedValue({
    severity_map: { block_at_or_above: 0.5, warn_above: 0, weights: { HIGH: 1, MEDIUM: 0.5, LOW: 0.2 } },
    flags: [
      { flag: "FABRICATED_ALLERGY", category: "medication", tier: "TIER_1", gradeable: true, owner_roles: ["risk_judge"] },
      { flag: "DURATION_FABRICATION", category: "fidelity", tier: "TIER_3", gradeable: true, owner_roles: [] },
    ],
  }),
}));

import FlagEditor from "./FlagEditor.jsx";
import ContractBuilder from "./ContractBuilder.jsx";
import KbPicker from "./KbPicker.jsx";
import { getOntology } from "../bff.js";

describe("FlagEditor (tool-flag_editor)", () => {
  it("reads the ontology via GET and returns severity_map + per-flag config", async () => {
    const onResult = vi.fn();
    render(<FlagEditor onResult={onResult} />);

    expect(await screen.findByText(/Flags & severity/i)).toBeInTheDocument();
    expect(getOntology).toHaveBeenCalledTimes(1);
    // owner_roles surfaced (read-only); the GLOBAL severity_map is a distinct section.
    expect(screen.getByText("FABRICATED_ALLERGY")).toBeInTheDocument();
    expect(screen.getByText(/Severity map \(global\)/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Apply config/i }));

    expect(onResult).toHaveBeenCalledTimes(1);
    const result = onResult.mock.calls[0][0];
    expect(result.severity_map.weights.HIGH).toBe(1);
    expect(result.flags).toHaveLength(2);
    expect(result.flags[0]).toMatchObject({ flag: "FABRICATED_ALLERGY", tier: "TIER_1", gradeable: true });
  });
});

describe("ContractBuilder (tool-contract_builder)", () => {
  it("collects a claim → tool-query → verdict contract and returns it", () => {
    const onResult = vi.fn();
    render(<ContractBuilder onResult={onResult} />);

    fireEvent.change(screen.getByLabelText("flag code"), { target: { value: "MEDICATION_NOT_IN_TRANSCRIPT" } });
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "Is the med present in the transcript?" } });
    fireEvent.click(screen.getByRole("button", { name: /Add contract/i }));

    expect(onResult).toHaveBeenCalledTimes(1);
    const c = onResult.mock.calls[0][0];
    expect(c).toMatchObject({
      contract_type: "presence_check",
      flag_code: "MEDICATION_NOT_IN_TRANSCRIPT",
      question: "Is the med present in the transcript?",
    });
    expect(c.params).toBeTypeOf("object");
    expect(c.version).toMatch(/v1$/);
  });

  it("disables Add until claim + question are filled", () => {
    render(<ContractBuilder onResult={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Add contract/i })).toBeDisabled();
  });
});

describe("KbPicker (tool-kb_picker)", () => {
  it("returns the bound kb_bindings + retrieval settings", async () => {
    const onResult = vi.fn();
    render(<KbPicker onResult={onResult} />);

    fireEvent.click(screen.getByRole("button", { name: /Bind KB/i }));

    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
    const r = onResult.mock.calls[0][0];
    expect(r.kb_bindings.length).toBeGreaterThan(0);
    expect(r.kb_bindings[0]).toMatchObject({ index: "hipaa-compliancev2" });
    expect(r.rerank).toBe(false); // off for structured/clinical KBs
  });
});
