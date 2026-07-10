/* ContractBuilder.test.jsx — FAUTH-1 (G1): the inline contract-authoring widget, surfaced
   by the agent (author_contract → tool-contract_builder), opens PRE-SEEDED with the in-context
   flag and saves via the EXISTING audited putGroundingContract write.

   Covers A2 (renders pre-seeded + saves with the seeded flag_code) and A4 (the inline type list
   is scoped to types that have a registered executor — a non-coder can't pick a contract_type that
   raises at grade time, R4). Mirrors VerdictCard.test.jsx (mock bff, render, fireEvent). The
   pre-existing inputs.test.jsx still covers the un-seeded persist/onResult/disabled paths. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// the widget self-persists via POST /v1/grounding-contract before firing onResult — mock it so
// mounting never reaches a real fetch (mirrors inputs.test.jsx + VerdictCard.test.jsx). FAUTH-2:
// ContractBuilder also fetches the live registered types on mount (getGroundingContractTypes) —
// mock it too, default a resolved set; individual tests override it (resolve/reject) for A3.
vi.mock("../bff.js", () => ({
  putGroundingContract: vi.fn().mockResolvedValue({ flag_code: "X", replaced: false, status: "ok" }),
  getGroundingContractTypes: vi.fn().mockResolvedValue({ contract_types: ["presence_check"], pack: "_core" }),
}));

import ContractBuilder, { CONTRACT_TYPES } from "./ContractBuilder.jsx";
import { putGroundingContract, getGroundingContractTypes } from "../bff.js";

describe("ContractBuilder — FAUTH-1 inline, pre-seeded by the in-context flag (A2)", () => {
  it("opens pre-filled with the seeded flagCode", () => {
    render(<ContractBuilder agent="ws0_default" flagCode="INFORMED_DISSENT_ERASURE" onResult={vi.fn()} />);
    // the flag-code field is pre-bound to the in-context flag (not blank) — R5.
    expect(screen.getByLabelText("flag code")).toHaveValue("INFORMED_DISSENT_ERASURE");
  });

  it("saves the seeded contract via the EXISTING putGroundingContract (the human's Save is the write)", async () => {
    putGroundingContract.mockClear();
    const onResult = vi.fn();
    render(<ContractBuilder agent="eval-1" flagCode="INFORMED_DISSENT_ERASURE" onResult={onResult} />);

    // the flag is pre-seeded; the human only adds the question, then Saves.
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "Is the refusal preserved?" } });
    fireEvent.click(screen.getByRole("button", { name: /Add contract/i }));

    await waitFor(() => expect(putGroundingContract).toHaveBeenCalledTimes(1));
    const [contract, agent] = putGroundingContract.mock.calls[0];
    expect(agent).toBe("eval-1");
    // the audited write carries the SEEDED flag_code — the card opened pre-bound to it.
    expect(contract.flag_code).toBe("INFORMED_DISSENT_ERASURE");
    expect(contract.question).toBe("Is the refusal preserved?");
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
  });

  it("the default (no seed) stays blank + back-compat (the un-seeded path is unchanged)", () => {
    render(<ContractBuilder agent="ws0_default" onResult={vi.fn()} />);
    expect(screen.getByLabelText("flag code")).toHaveValue("");
  });
});

describe("ContractBuilder — no broken-type footgun (A4 / R4)", () => {
  it("the inline type list contains ONLY types with a registered executor", () => {
    // presence_check (core suppress executor) is the always-registered floor type; the canonical
    // grounding types add_grounding_contract advertises (snomed_subsumption / record_presence) are
    // pack-registered. The broken types that make ground() RAISE at grade time are GONE.
    expect(CONTRACT_TYPES).toContain("presence_check");
    for (const broken of ["negation_check", "code_match", "range_check"]) {
      expect(CONTRACT_TYPES).not.toContain(broken);
    }
  });

  it("the type selector offers only the registered types (a non-coder can't pick a raising type)", () => {
    render(<ContractBuilder agent="ws0_default" flagCode="X" onResult={vi.fn()} />);
    // the Select renders an option per registered type; none of the broken types is selectable.
    for (const broken of ["negation_check", "code_match", "range_check"]) {
      expect(screen.queryAllByText(broken)).toHaveLength(0);
    }
  });
});

// Radix Select renders its option items into a portal only when OPENED — open the trigger first
// (Radix opens on pointerDown, not click; the jsdom pointer-capture + scrollIntoView shims live in
// src/test/setup.js), then the SelectItems become queryable.
const openTypeSelect = () =>
  fireEvent.pointerDown(screen.getByLabelText("contract type"), { button: 0, ctrlKey: false, pointerType: "mouse" });

describe("ContractBuilder — the live type list drives the UI, with a fallback (FAUTH-2 / A3)", () => {
  it("fetches the active pack's registered types on mount and drives the Select from them", async () => {
    getGroundingContractTypes.mockClear();
    // a pack registry that DIFFERS from the static fallback — proves the fetched set is used.
    getGroundingContractTypes.mockResolvedValueOnce({
      contract_types: ["presence_check", "snomed_subsumption"],
      pack: "healthcare",
    });
    render(<ContractBuilder agent="ws0_default" flagCode="X" onResult={vi.fn()} />);

    await waitFor(() => expect(getGroundingContractTypes).toHaveBeenCalledTimes(1));
    openTypeSelect();
    // the fetched (pack-true) set drives the options; record_presence (static fallback only) is
    // NOT offered, since the fetch returned a narrower set. (UX-COPY: keys render as plain labels.)
    expect((await screen.findAllByText("Medical-term match")).length).toBeGreaterThan(0);
    expect(screen.queryAllByText("Was actually recorded")).toHaveLength(0);
  });

  it("falls back to the static CONTRACT_TYPES when the fetch REJECTS (offline-safe, no crash)", async () => {
    getGroundingContractTypes.mockClear();
    getGroundingContractTypes.mockRejectedValueOnce(new Error("offline"));
    render(<ContractBuilder agent="ws0_default" flagCode="X" onResult={vi.fn()} />);

    await waitFor(() => expect(getGroundingContractTypes).toHaveBeenCalledTimes(1));
    openTypeSelect();
    // the rejected fetch keeps the static fallback selectable (never crashes) — every static type
    // is offered. (UX-COPY: the type KEY is preserved as the option value but renders as a plain label.)
    const TYPE_LABEL = {
      presence_check: "Must be in the record",
      snomed_subsumption: "Medical-term match",
      record_presence: "Was actually recorded",
    };
    for (const t of CONTRACT_TYPES) {
      expect((await screen.findAllByText(TYPE_LABEL[t])).length).toBeGreaterThan(0);
    }
  });
});

describe("ContractBuilder — FAUTH-3 prose→params pre-fill (A5)", () => {
  it("pre-fills the editable params textarea from suggested_params (not the inert default), no auto-save", () => {
    putGroundingContract.mockClear();
    // the agent's assist suggestion (a presence_check skeleton); the card opens PRE-FILLED with it.
    const sp = { med_source: "transcript.text", dosage_regex: "\\b\\d+\\b", token_min_len: 4, noise_tokens: ["the"] };
    render(
      <ContractBuilder agent="ws0_default" flagCode="MEDICATION_NOT_IN_TRANSCRIPT" suggested_params={sp} onResult={vi.fn()} />,
    );
    const ta = screen.getByLabelText("params json");
    // the suggested values are pre-filled; the inert {"source":"response.claims"} default is gone.
    expect(ta).toHaveValue(JSON.stringify(sp, null, 2));
    expect(ta.value).not.toContain("response.claims");
    // the suggestion is a DRAFT — the textarea stays editable.
    fireEvent.change(ta, { target: { value: '{"med_source":"x","dosage_regex":"y"}' } });
    expect(ta).toHaveValue('{"med_source":"x","dosage_regex":"y"}');
    // SPINE INVARIANT (UI side): surfacing the pre-filled card writes NOTHING — only the human's
    // explicit Save calls putGroundingContract.
    expect(putGroundingContract).not.toHaveBeenCalled();
  });

  it("the un-seeded params textarea keeps the inert default (back-compat)", () => {
    render(<ContractBuilder agent="ws0_default" flagCode="X" onResult={vi.fn()} />);
    expect(screen.getByLabelText("params json").value).toContain("response.claims");
  });
});

describe("ContractBuilder — FAUTH-3 / S-BS-143 seeded contract_type (the FLOOR direction)", () => {
  it("opens on the seeded value_presence type and Saves it (the FLOOR direction, not presence_check)", async () => {
    putGroundingContract.mockClear();
    const onResult = vi.fn();
    render(
      <ContractBuilder
        agent="narrative_default"
        flagCode="DISSENT_ERASURE"
        contract_type="value_presence"
        suggested_params={{ value_regex: "refus\\w*", source_path: "transcript" }}
        onResult={onResult}
      />,
    );
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "Is the refusal recorded?" } });
    fireEvent.click(screen.getByRole("button", { name: /Add contract/i }));

    await waitFor(() => expect(putGroundingContract).toHaveBeenCalledTimes(1));
    const [contract] = putGroundingContract.mock.calls[0];
    // the card opened on the agent-chosen FLOOR direction — the authored contract is value_presence,
    // NOT the presence_check suppress default (which can never flip APPROVE→BLOCK).
    expect(contract.contract_type).toBe("value_presence");
  });

  it("offers the seeded type as selectable even when the live/fallback set omits it", async () => {
    // the default mock returns only presence_check — the seeded value_presence must still be merged
    // into the options so a non-coder can keep / re-pick it.
    getGroundingContractTypes.mockClear();
    render(
      <ContractBuilder agent="narrative_default" flagCode="DISSENT_ERASURE" contract_type="value_presence" onResult={vi.fn()} />,
    );
    await waitFor(() => expect(getGroundingContractTypes).toHaveBeenCalledTimes(1));
    openTypeSelect();
    expect((await screen.findAllByText("value_presence")).length).toBeGreaterThan(0);
  });

  it("defaults to presence_check when no contract_type is seeded (back-compat)", async () => {
    putGroundingContract.mockClear();
    render(<ContractBuilder agent="ws0_default" flagCode="X" onResult={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "present?" } });
    fireEvent.click(screen.getByRole("button", { name: /Add contract/i }));
    await waitFor(() => expect(putGroundingContract).toHaveBeenCalledTimes(1));
    expect(putGroundingContract.mock.calls[0][0].contract_type).toBe("presence_check");
  });
});

describe("ContractBuilder — reads as rule authorship, not form-filling (INLINE-IMPACT-1)", () => {
  it("shows a live 'Rule in English' restatement of the contract", () => {
    render(
      <ContractBuilder
        agent="narrative_default"
        flagCode="DISSENT_ERASURE"
        contract_type="value_presence"
        suggested_params={{ value_regex: "refus\\w*", source_path: "transcript" }}
        question="Is the patient's refusal preserved in the note?"
        onResult={vi.fn()}
      />,
    );
    const en = screen.getByTestId("rule-in-english").textContent;
    expect(en).toMatch(/Dissent erasure/i); // the flag the rule guards (rendered as a plain label)
    expect(en).toMatch(/refusal preserved/i); // the question, restated
    expect(en).toMatch(/flag the result/i); // the result direction in plain words
  });

  it("the 'Rule in English' restatement updates LIVE as the human edits", () => {
    render(<ContractBuilder agent="x" flagCode="F" onResult={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "Was consent documented?" } });
    expect(screen.getByTestId("rule-in-english").textContent).toMatch(/Was consent documented/);
  });

  it("shows an 'AI-suggested' pill when the assist seeded the params", () => {
    render(
      <ContractBuilder agent="x" flagCode="F" suggested_params={{ value_regex: "a", source_path: "t" }} onResult={vi.fn()} />,
    );
    expect(screen.getByText(/AI-suggested/i)).toBeInTheDocument();
  });

  it("no 'AI-suggested' pill when the human starts from scratch (not seeded)", () => {
    render(<ContractBuilder agent="x" flagCode="F" onResult={vi.fn()} />);
    expect(screen.queryByText(/AI-suggested/i)).toBeNull();
  });

  it("frames it as an Automated fact-check prominently (not a buried caption)", () => {
    render(<ContractBuilder agent="x" flagCode="F" onResult={vi.fn()} />);
    // the prominent header chip (capitalized) — distinct from the lowercase "automated fact-check"
    // that also appears in the Result-direction line.
    expect(screen.getByText("Automated fact-check")).toBeInTheDocument();
  });
});
