/* inputs.test.jsx — A3: FlagEditor / ContractBuilder / KbPicker collect input and
   return a result object via onResult(). FlagEditor reads the ontology via GET only
   (mocked here) — no PUT this phase. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// FlagEditor reads GET /v1/ontology + persists via PUT; ContractBuilder (EVAL-FLOW W1b) now
// self-persists via POST /v1/grounding-contract before firing onResult — mock all three.
vi.mock("../bff.js", () => ({
  getOntology: vi.fn().mockResolvedValue({
    domain: "clinical",
    ontology_version: "clinical/1",
    severity_map: { block_at_or_above: 0.5, warn_above: 0, weights: { HIGH: 1, MEDIUM: 0.5, LOW: 0.2 } },
    flags: [
      { flag: "FABRICATED_ALLERGY", category: "medication", tier: "TIER_1", gradeable: true, owner_roles: ["risk_judge"] },
      { flag: "DURATION_FABRICATION", category: "fidelity", tier: "TIER_3", gradeable: true, owner_roles: [] },
    ],
  }),
  putOntology: vi.fn().mockResolvedValue({ status: "ok", working_copy: "/tmp/ont/ws0_default.json" }),
  putGroundingContract: vi.fn().mockResolvedValue({ flag_code: "X", replaced: false, status: "ok" }),
  // FAUTH-2: ContractBuilder fetches the live registered types on mount — mock it so these
  // pre-existing tests don't crash on the new useEffect (back-compat / R4).
  getGroundingContractTypes: vi.fn().mockResolvedValue({ contract_types: ["presence_check"], pack: "_core" }),
}));

import FlagEditor from "./FlagEditor.jsx";
import ContractBuilder from "./ContractBuilder.jsx";
import KbPicker from "./KbPicker.jsx";
import { getOntology, putOntology, putGroundingContract } from "../bff.js";

describe("FlagEditor (tool-flag_editor)", () => {
  it("reads the ontology via GET and returns severity_map + per-flag config", async () => {
    const onResult = vi.fn();
    render(<FlagEditor onResult={onResult} />);

    expect(await screen.findByText(/Checks & severity/i)).toBeInTheDocument();
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

  it("persists a draft via PUT /v1/ontology, merging edits into the FULL ontology (D4)", async () => {
    putOntology.mockClear();
    render(<FlagEditor onResult={vi.fn()} />);
    expect(await screen.findByText(/Checks & severity/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Persist draft/i }));

    await waitFor(() => expect(putOntology).toHaveBeenCalledTimes(1));
    const body = putOntology.mock.calls[0][0];
    // the PUT body is the FULL ontology (round-trips through from_dict), not the partial
    expect(body.domain).toBe("clinical");
    expect(body.ontology_version).toBe("clinical/1");
    expect(body.flags.map((f) => f.flag)).toContain("FABRICATED_ALLERGY");
    expect(body.severity_map).toBeTruthy();
    expect(await screen.findByText(/draft saved/i)).toBeInTheDocument();
  });

  it("surfaces a rejected PUT (422) in the footer", async () => {
    putOntology.mockRejectedValueOnce(new Error("PUT /v1/ontology → 422: snapshot violation"));
    render(<FlagEditor onResult={vi.fn()} />);
    expect(await screen.findByText(/Checks & severity/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Persist draft/i }));
    expect(await screen.findByText(/snapshot violation/i)).toBeInTheDocument();
  });
});

describe("ContractBuilder (tool-contract_builder)", () => {
  // EVAL-FLOW (W1b/R1): "Add contract" now PERSISTS to ontology.verification_contracts (the
  // grade's store) via POST /v1/grounding-contract BEFORE firing onResult — the honest tick.
  // (The prior test asserted a synchronous onResult with no write; that was correct for the
  // old card but is the behavior W1b changes — EXECUTOR.md §4.)
  it("persists the contract via POST /v1/grounding-contract THEN returns it (honest tick)", async () => {
    putGroundingContract.mockClear();
    const onResult = vi.fn();
    render(<ContractBuilder agent="eval-1" onResult={onResult} />);

    fireEvent.change(screen.getByLabelText("flag code"), { target: { value: "MEDICATION_NOT_IN_TRANSCRIPT" } });
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "Is the med present in the transcript?" } });
    fireEvent.click(screen.getByRole("button", { name: /Add contract/i }));

    // the audited write fires first, against the active agent…
    await waitFor(() => expect(putGroundingContract).toHaveBeenCalledTimes(1));
    const [contract, agent] = putGroundingContract.mock.calls[0];
    expect(agent).toBe("eval-1");
    expect(contract).toMatchObject({
      contract_type: "presence_check",
      flag_code: "MEDICATION_NOT_IN_TRANSCRIPT",
      question: "Is the med present in the transcript?",
    });
    // …then onResult signals up (so captureSetup → refreshJourney ticks Ground truth).
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
    const c = onResult.mock.calls[0][0];
    expect(c.params).toBeTypeOf("object");
    expect(c.version).toMatch(/v1$/);
    expect(await screen.findByText(/added to setup/i)).toBeInTheDocument();
  });

  it("a rejected write (404 unknown flag) surfaces inline and does NOT fire onResult (no manufactured tick)", async () => {
    putGroundingContract.mockRejectedValueOnce(new Error("POST /v1/grounding-contract → 404: unknown flag"));
    const onResult = vi.fn();
    render(<ContractBuilder agent="eval-1" onResult={onResult} />);

    fireEvent.change(screen.getByLabelText("flag code"), { target: { value: "NOPE" } });
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "q" } });
    fireEvent.click(screen.getByRole("button", { name: /Add contract/i }));

    expect(await screen.findByText(/unknown flag/i)).toBeInTheDocument();
    expect(onResult).not.toHaveBeenCalled(); // the rail can never tick on a failed write
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
    expect(r.kb_bindings[0]).toMatchObject({ index: "knowledge-base" });
    expect(r.rerank).toBe(false); // off for structured KBs
  });
});
