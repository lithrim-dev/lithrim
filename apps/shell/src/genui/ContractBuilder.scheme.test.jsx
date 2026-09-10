/* ContractBuilder.scheme.test.jsx — UI-JOURNEY-1 (B10): the contract version is a scheme. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  putGroundingContract: vi.fn().mockResolvedValue({ flag_code: "X", replaced: false, status: "ok" }),
  getGroundingContractTypes: vi.fn().mockResolvedValue({ contract_types: ["presence_check"], pack: "_core" }),
}));

import ContractBuilder from "./ContractBuilder.jsx";

describe("ContractBuilder — version scheme", () => {
  it("shows <flag>/v1 as the default version and explains the bump rule", async () => {
    render(<ContractBuilder agent="ws0_default" onResult={vi.fn()} />);
    const note = await screen.findByTestId("contract-version-scheme");
    expect(note.textContent).toMatch(/version contract\/v1/);
    expect(note.textContent).toMatch(/bump N when the check's meaning changes/);
  });
});
