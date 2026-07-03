/* FlagEditor.text.test.jsx — CRITERION-TEXT-1: the criterion TEXT (definition / when_to_use /
   when_NOT_to_use) is EDITABLE per flag, not just tier/gradeable. when_to_use is the field the
   judge-prompt bridge renders (the AUTHORED REFINEMENT lens line); before this the only way to
   reword it was a raw whole-ontology PUT. Covers: expand a row → the current text shows; edit →
   "Persist draft" round-trips the reword through putOntology with sibling flags + untouched
   fields preserved; "Apply config" returns the text into setup state. */
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
  severity_map: { block_at_or_above: 0.5, warn_above: 0, weights: { HIGH: 0.9, MEDIUM: 0.5, LOW: 0.2 } },
  flags: [
    {
      flag: "FABRICATED_CLAIM",
      category: "faithfulness",
      definition: "old definition",
      when_to_use: "old lens",
      when_NOT_to_use: "old anti-lens",
      owner_roles: ["risk_judge"],
      tier: "TIER_1",
      gradeable: true,
      reliability_pillar: "faithfulness",
    },
    {
      flag: "STYLE_VIOLATION",
      category: "style",
      definition: "style def",
      when_to_use: "style lens",
      when_NOT_to_use: "",
      owner_roles: [],
      tier: "TIER_3",
      gradeable: false,
    },
  ],
  questions: [],
  verification_contracts: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  getOntology.mockResolvedValue(JSON.parse(JSON.stringify(ONT)));
  putOntology.mockResolvedValue({ status: "ok" });
});

async function renderReady(props = {}) {
  const utils = render(<FlagEditor agent="ws0_default" {...props} />);
  await waitFor(() => expect(screen.getByText("FABRICATED_CLAIM")).toBeInTheDocument());
  return utils;
}

describe("FlagEditor — CRITERION-TEXT-1 per-flag criterion text editing", () => {
  it("expanding a flag row reveals the current criterion text", async () => {
    await renderReady();
    fireEvent.click(screen.getByLabelText("edit criterion text for FABRICATED_CLAIM"));
    expect(screen.getByLabelText("when to use for FABRICATED_CLAIM")).toHaveValue("old lens");
    expect(screen.getByLabelText("when NOT to use for FABRICATED_CLAIM")).toHaveValue("old anti-lens");
    expect(screen.getByLabelText("definition for FABRICATED_CLAIM")).toHaveValue("old definition");
  });

  it("a reworded when_to_use persists via putOntology; untouched fields + siblings preserved", async () => {
    await renderReady();
    fireEvent.click(screen.getByLabelText("edit criterion text for FABRICATED_CLAIM"));
    fireEvent.change(screen.getByLabelText("when to use for FABRICATED_CLAIM"), {
      target: { value: "1) The response cites a NUMBER absent from the source." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Persist draft/i }));
    await waitFor(() => expect(putOntology).toHaveBeenCalledTimes(1));
    const [body] = putOntology.mock.calls[0];
    const fab = body.flags.find((f) => f.flag === "FABRICATED_CLAIM");
    expect(fab.when_to_use).toBe("1) The response cites a NUMBER absent from the source.");
    expect(fab.when_NOT_to_use).toBe("old anti-lens"); // untouched field preserved
    expect(fab.definition).toBe("old definition");
    expect(fab.tier).toBe("TIER_1");
    expect(fab.reliability_pillar).toBe("faithfulness"); // pass-through fields survive the merge
    expect(body.flags.find((f) => f.flag === "STYLE_VIOLATION")).toMatchObject({
      when_to_use: "style lens",
      definition: "style def",
    });
  });

  it("Apply config returns the edited criterion text into setup state", async () => {
    const onResult = vi.fn();
    await renderReady({ onResult });
    fireEvent.click(screen.getByLabelText("edit criterion text for FABRICATED_CLAIM"));
    fireEvent.change(screen.getByLabelText("when NOT to use for FABRICATED_CLAIM"), {
      target: { value: "the figure is a unit conversion" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Apply config/i }));
    expect(onResult).toHaveBeenCalledTimes(1);
    const result = onResult.mock.calls[0][0];
    const fab = result.flags.find((f) => f.flag === "FABRICATED_CLAIM");
    expect(fab.when_NOT_to_use).toBe("the figure is a unit conversion");
    expect(fab.when_to_use).toBe("old lens");
  });
});
