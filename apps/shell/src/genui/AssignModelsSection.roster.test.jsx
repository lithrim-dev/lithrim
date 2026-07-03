/* AssignModelsSection.roster.test.jsx — REPRO-1 R2a/R2b: the N-model council is authorable.

   R2a: the binding rows derive from the ACTIVE workspace roster (getCouncilRoster's
   panel ∪ selectable — which includes JudgeBuilder-authored roles), not a hardcoded trio; the
   setup-complete gate counts the roles that will actually grade (the reviewer_roster override
   when set, else the panel), so a 4-clone council can be ready without the pack trio bound.
   R2b: a CUSTOM roster mode — pick any subset of reviewers (checkboxes) → setCouncilRoster
   persists the multi-role roster; loading an existing multi-roster shows custom mode.
   The empty-roster fallback (panel: []) keeps the v2 trio rows — the existing consolidate
   tests pin that back-compat. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { getModelCatalog, bindRole, getCouncilRoster, setCouncilRoster } = vi.hoisted(() => ({
  getModelCatalog: vi.fn(),
  bindRole: vi.fn(),
  getCouncilRoster: vi.fn(),
  setCouncilRoster: vi.fn().mockResolvedValue({ status: "ok" }),
}));
vi.mock("../bff.js", () => ({ getModelCatalog, bindRole, getCouncilRoster, setCouncilRoster }));

import AssignModelsSection from "./AssignModelsSection.jsx";

const CLONES = ["reviewer_gpt41", "reviewer_gpt55", "reviewer_opus", "reviewer_sonnet"];
const ROSTER = {
  panel: CLONES,
  selectable: CLONES,
  reviewer_roster: null,
  recommendation: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  getModelCatalog.mockResolvedValue({ providers: {} });
  getCouncilRoster.mockResolvedValue(JSON.parse(JSON.stringify(ROSTER)));
  setCouncilRoster.mockResolvedValue({ status: "ok" });
});

describe("AssignModelsSection — roster-derived rows (R2a)", () => {
  it("renders a binding row for EVERY roster reviewer (authored roles included) + chat", async () => {
    render(<AssignModelsSection connected={["openai", "anthropic"]} bindings={{}} agent="a" />);
    for (const role of CLONES) {
      expect(await screen.findByTestId(`role-bind-row-${role}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId("role-bind-row-chat_assistant")).toBeInTheDocument();
    // the hardcoded v2 trio is NOT rendered when the roster names other reviewers
    expect(screen.queryByTestId("role-bind-row-risk_judge")).toBeNull();
  });

  it("the ready gate counts the roles that will actually grade", async () => {
    const bindings = Object.fromEntries(
      [...CLONES, "chat_assistant"].map((r) => [r, { provider: "openai", model: "gpt-4.1" }]),
    );
    render(<AssignModelsSection connected={["openai"]} bindings={bindings} agent="a" />);
    const status = await screen.findByTestId("setup-complete-status");
    await waitFor(() => expect(status).toHaveTextContent(/ready/i));
    expect(status).not.toHaveTextContent(/not ready|still needs/i);
  });

  it("a single-reviewer roster only requires THAT reviewer (+ chat) to be ready", async () => {
    getCouncilRoster.mockResolvedValue({ ...ROSTER, reviewer_roster: ["reviewer_gpt41"] });
    const bindings = {
      reviewer_gpt41: { provider: "openai", model: "gpt-4.1" },
      chat_assistant: { provider: "openai", model: "gpt-4.1" },
    };
    render(<AssignModelsSection connected={["openai"]} bindings={bindings} agent="a" />);
    const status = await screen.findByTestId("setup-complete-status");
    await waitFor(() => expect(status).toHaveTextContent(/ready/i));
    expect(status).not.toHaveTextContent(/not ready|still needs/i);
  });
});

describe("AssignModelsSection — custom multi-roster (R2b)", () => {
  it("custom mode persists a checked subset via setCouncilRoster", async () => {
    render(<AssignModelsSection connected={["openai"]} bindings={{}} agent="a" />);
    fireEvent.click(await screen.findByTestId("reviewer-mode-custom"));
    fireEvent.click(screen.getByTestId("roster-check-reviewer_gpt41"));
    await waitFor(() => expect(setCouncilRoster).toHaveBeenCalled());
    setCouncilRoster.mockClear();
    fireEvent.click(screen.getByTestId("roster-check-reviewer_sonnet"));
    await waitFor(() =>
      expect(setCouncilRoster).toHaveBeenCalledWith({
        agent: "a",
        roster: ["reviewer_gpt41", "reviewer_sonnet"],
      }),
    );
  });

  it("an existing multi-roster loads as custom mode with its members checked", async () => {
    getCouncilRoster.mockResolvedValue({
      ...ROSTER,
      reviewer_roster: ["reviewer_gpt41", "reviewer_opus"],
    });
    render(<AssignModelsSection connected={["openai"]} bindings={{}} agent="a" />);
    const check = await screen.findByTestId("roster-check-reviewer_gpt41");
    expect(check).toBeChecked();
    expect(screen.getByTestId("roster-check-reviewer_opus")).toBeChecked();
    expect(screen.getByTestId("roster-check-reviewer_sonnet")).not.toBeChecked();
  });
});
