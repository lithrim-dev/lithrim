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
// mounting never reaches a real fetch (mirrors inputs.test.jsx + VerdictCard.test.jsx).
vi.mock("../bff.js", () => ({
  putGroundingContract: vi.fn().mockResolvedValue({ flag_code: "X", replaced: false, status: "ok" }),
}));

import ContractBuilder, { CONTRACT_TYPES } from "./ContractBuilder.jsx";
import { putGroundingContract } from "../bff.js";

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
