/* CriterionBuilder.test.jsx — NARR-5-CRIT-b: the inline criterion-authoring widget, surfaced by
   the agent (author_criterion → tool-criterion_builder), opens pre-seeded with the in-context
   code/tier/owner and MINTS via the sanctioned POST /v1/criterion write.

   Covers: renders pre-seeded; the human's Save (and ONLY the Save) calls postCriterion + fires
   onResult (the SPINE/CONTAINMENT invariant — surfacing the card writes nothing); local code-shape
   validation gates Save (mirror of the server F1 guard). Mirrors ContractBuilder.test.jsx. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// the widget mints via POST /v1/criterion before firing onResult — mock it so mounting never reaches
// a real fetch (mirrors ContractBuilder.test.jsx).
vi.mock("../bff.js", () => ({
  postCriterion: vi.fn().mockResolvedValue({ status: "ok", code: "EVERY_DOSE_IN_SOAP" }),
}));

import CriterionBuilder, { TIERS } from "./CriterionBuilder.jsx";
import { postCriterion } from "../bff.js";

describe("CriterionBuilder — NARR-5-CRIT-b inline, pre-seeded by the agent", () => {
  it("opens pre-filled with the seeded code + owner", () => {
    render(
      <CriterionBuilder agent="ws0_default" code="EVERY_DOSE_IN_SOAP" tier="TIER_2" owner_role="faithfulness_judge" onResult={vi.fn()} />,
    );
    expect(screen.getByLabelText("criterion code")).toHaveValue("EVERY_DOSE_IN_SOAP");
    expect(screen.getByLabelText("owner role")).toHaveValue("faithfulness_judge");
  });

  it("the human's Save mints via postCriterion (the SOLE write) and fires onResult", async () => {
    postCriterion.mockClear();
    const onResult = vi.fn();
    render(
      <CriterionBuilder agent="eval-1" code="EVERY_DOSE_IN_SOAP" tier="TIER_2" owner_role="faithfulness_judge" onResult={onResult} />,
    );
    // SPINE INVARIANT (UI side): surfacing the pre-filled card writes NOTHING until the human Saves.
    expect(postCriterion).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Add criterion/i }));
    await waitFor(() => expect(postCriterion).toHaveBeenCalledTimes(1));
    const [criterion, agent] = postCriterion.mock.calls[0];
    expect(agent).toBe("eval-1");
    expect(criterion).toMatchObject({
      code: "EVERY_DOSE_IN_SOAP",
      tier: "TIER_2",
      owner_role: "faithfulness_judge",
    });
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
  });

  it("gates Save on a valid code + owner (a malformed code does not write)", () => {
    postCriterion.mockClear();
    render(<CriterionBuilder agent="ws0_default" code="lower case" owner_role="faithfulness_judge" onResult={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /Add criterion/i });
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(postCriterion).not.toHaveBeenCalled();
  });

  it("the default (no seed) is blank with Save disabled (back-compat / empty card)", () => {
    render(<CriterionBuilder agent="ws0_default" onResult={vi.fn()} />);
    expect(screen.getByLabelText("criterion code")).toHaveValue("");
    expect(screen.getByRole("button", { name: /Add criterion/i })).toBeDisabled();
    expect(TIERS).toEqual(["TIER_1", "TIER_2", "TIER_3"]);
  });

  // CRITERION-TEXT-1: the criterion TEXT (the when_to_use lens that renders into the judge's
  // prompt) is collected at mint time — the field is no longer unauthorable from the UI.
  it("collects when_to_use / when_NOT_to_use into the mint payload", async () => {
    postCriterion.mockClear();
    render(
      <CriterionBuilder agent="eval-1" code="EVERY_DOSE_IN_SOAP" tier="TIER_2" owner_role="faithfulness_judge" onResult={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText("when to use"), {
      target: { value: "1) A dose stated in the transcript is absent from the note." },
    });
    fireEvent.change(screen.getByLabelText("when NOT to use"), {
      target: { value: "The dose appears with different but equivalent units." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Add criterion/i }));
    await waitFor(() => expect(postCriterion).toHaveBeenCalledTimes(1));
    const [criterion] = postCriterion.mock.calls[0];
    expect(criterion.when_to_use).toBe("1) A dose stated in the transcript is absent from the note.");
    expect(criterion.when_NOT_to_use).toBe("The dose appears with different but equivalent units.");
  });

  it("pre-seeds the criterion text drafted by the agent (author_criterion seed)", () => {
    render(
      <CriterionBuilder
        agent="ws0_default"
        code="EVERY_DOSE_IN_SOAP"
        owner_role="faithfulness_judge"
        definition="drafted definition"
        when_to_use="drafted lens"
        when_NOT_to_use="drafted anti-lens"
        onResult={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("definition")).toHaveValue("drafted definition");
    expect(screen.getByLabelText("when to use")).toHaveValue("drafted lens");
    expect(screen.getByLabelText("when NOT to use")).toHaveValue("drafted anti-lens");
  });
});
