/* FlagEditor.contextfields.test.jsx — REPRO-1 R1b: the ontology's `grading_context_fields`
   (which case fields fold into the judge-visible grading context as SOURCE RECORD sections) is
   authorable in the checks editor — user DATA, never code. Persists via the same audited
   PUT /v1/ontology round-trip as the rest of the card; SIGNATURE-1 then stales prior heads. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getOntology: vi.fn(),
  putOntology: vi.fn().mockResolvedValue({ status: "ok" }),
}));

import FlagEditor from "./FlagEditor.jsx";
import { getOntology, putOntology } from "../bff.js";

const ONT = {
  ontology_version: "test/1",
  domain: "content_review",
  severity_map: { block_at_or_above: 0.5, warn_above: 0, weights: { HIGH: 0.9 } },
  grading_context_fields: ["patient_profile"],
  flags: [
    {
      flag: "FABRICATED_CLAIM", category: "faithfulness", definition: "d",
      when_to_use: "w", when_NOT_to_use: "", owner_roles: [], tier: "TIER_1", gradeable: true,
    },
  ],
  questions: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  getOntology.mockResolvedValue(JSON.parse(JSON.stringify(ONT)));
  putOntology.mockResolvedValue({ status: "ok" });
});

async function renderReady() {
  const utils = render(<FlagEditor agent="ws0_default" />);
  await waitFor(() => expect(screen.getByText("FABRICATED_CLAIM")).toBeInTheDocument());
  return utils;
}

describe("FlagEditor — grading context fields (R1b)", () => {
  it("shows the declared fields and persists an edit through the ontology round-trip", async () => {
    await renderReady();
    const input = screen.getByLabelText("grading context fields");
    expect(input).toHaveValue("patient_profile");
    fireEvent.change(input, { target: { value: "patient_profile, account_record" } });
    fireEvent.click(screen.getByRole("button", { name: /Persist draft/i }));
    await waitFor(() => expect(putOntology).toHaveBeenCalledTimes(1));
    const [body] = putOntology.mock.calls[0];
    expect(body.grading_context_fields).toEqual(["patient_profile", "account_record"]);
    expect(body.flags[0].when_to_use).toBe("w"); // the rest of the round-trip is untouched
  });

  it("an empty declaration persists as an absent/empty list, never a ['']", async () => {
    await renderReady();
    fireEvent.change(screen.getByLabelText("grading context fields"), { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: /Persist draft/i }));
    await waitFor(() => expect(putOntology).toHaveBeenCalledTimes(1));
    const [body] = putOntology.mock.calls[0];
    expect(body.grading_context_fields ?? []).toEqual([]);
  });
});
