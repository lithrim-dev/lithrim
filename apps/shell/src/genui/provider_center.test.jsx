/* provider_center.test.jsx — CONNECT-AI-CONSOLIDATE-1: the 2-section Connect AI surface.

   (Reshaped from the PROVIDER-CENTER-B provider-first test, which exercised the now-DELETED
   ProviderPicker/ModelRegistry/ConsumerBind shape.) The panel is now TWO sections — Providers (the
   ONE place a key is entered) + Assign models (FOUR consumer rows incl. the compulsory cross-provider
   chat_assistant) — plus the LeftRail session-menu open/close affordance. The deep section behavior
   lives in connect_ai_consolidate.test.jsx; this file pins the panel shape + the rail integration.

   A: the panel renders the two sections (Providers + Assign models); the retired sections are gone.
   B: the connected-providers list renders from getRoleBindings.connected_providers.
   C: the LeftRail "Connect AI" menu item opens the panel; close dismisses it. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { configProvider, getProviderStatus, getModelCatalog, bindRole, getRoleBindings, getCouncilRoster, setCouncilRoster,
  hasStoredToken, logout, signIn } = vi.hoisted(() => ({
  configProvider: vi.fn(),
  getProviderStatus: vi.fn(),
  getModelCatalog: vi.fn(),
  bindRole: vi.fn(),
  getRoleBindings: vi.fn(),
  getCouncilRoster: vi.fn().mockResolvedValue({ panel: [], reviewer_roster: null }),
  setCouncilRoster: vi.fn().mockResolvedValue({ status: "ok" }),
  // UI-LOGIN-1 / SESSION-MENU-1: LeftRail reads these for the session-menu affordance.
  hasStoredToken: vi.fn(),
  logout: vi.fn(),
  signIn: vi.fn(),
}));

vi.mock("../bff.js", () => ({
  configProvider, getProviderStatus, getModelCatalog, bindRole, getRoleBindings, getCouncilRoster, setCouncilRoster,
  hasStoredToken, logout, signIn,
}));
// the LeftRail lives in panes.jsx (one dir up from genui/); mock its bff path too.
vi.mock("../../bff.js", () => ({
  configProvider, getProviderStatus, getModelCatalog, bindRole, getRoleBindings, getCouncilRoster, setCouncilRoster,
  hasStoredToken, logout, signIn,
}));

import ProviderSettings from "./ProviderSettings.jsx";

const CATALOG = {
  providers: {
    openai: [{ model: "gpt-4o", logprobs: true, context_window: 128000, cost_tier: "mid" }],
    anthropic: [{ model: "claude-3-5-sonnet-latest", logprobs: false, context_window: 200000, cost_tier: "mid" }],
    gemini: [{ model: "gemini-1.5-pro", logprobs: false, context_window: 1000000, cost_tier: "mid" }],
    azure: { models: [], note: "Azure is deployment-name based — type your deployment." },
  },
};
const BINDINGS = {
  roles: { risk_judge: null, policy_judge: null, faithfulness_judge: null, chat_assistant: null },
  connected_providers: ["openai", "anthropic", "gemini"],
};

beforeEach(() => {
  configProvider.mockReset().mockResolvedValue({ ok: true, plane: "grading", provider: "openai", last_tested: "2026-06-25T00:00:00+00:00" });
  getProviderStatus.mockReset().mockResolvedValue({ planes: {} });
  getModelCatalog.mockReset().mockResolvedValue(CATALOG);
  bindRole.mockReset().mockResolvedValue({ ok: true });
  getRoleBindings.mockReset().mockResolvedValue(BINDINGS);
  hasStoredToken.mockReset().mockReturnValue(false);
  logout.mockReset();
  signIn.mockReset();
});

describe("CONNECT-AI-CONSOLIDATE-1 — the 2-section panel shape", () => {
  it("A: renders the two sections (Providers + Assign models); the retired sections are gone", async () => {
    render(<ProviderSettings />);
    expect(await screen.findByTestId("providers-section")).toBeInTheDocument();
    expect(screen.getByTestId("assign-models-section")).toBeInTheDocument();
    expect(screen.queryByTestId("provider-picker-section")).toBeNull();
    expect(screen.queryByTestId("model-registry-section")).toBeNull();
    expect(screen.queryByTestId("consumer-bind-section")).toBeNull();
  });

  // F4: providers/bindings are global (accepted behavior) — a subtle clarity note so a "fresh"
  // workspace's pre-connected provider doesn't read as a bug.
  it("F4: notes that providers + bindings are shared across all workspaces", async () => {
    render(<ProviderSettings />);
    expect(await screen.findByTestId("provider-scope-hint")).toHaveTextContent(/shared across all your workspaces/i);
  });

  it("B: the connected-providers list renders from getRoleBindings.connected_providers", async () => {
    render(<ProviderSettings />);
    expect(await screen.findByTestId("providers-connected-row-openai")).toBeInTheDocument();
    expect(screen.getByTestId("providers-connected-row-gemini")).toBeInTheDocument();
    // a no-logprobs provider carries the ⚠ hint in its row
    expect(screen.getByTestId("providers-connected-row-gemini")).toHaveTextContent(/no logprobs/i);
  });
});

describe("REVIEWER-MODE — single vs multiple reviewers (Assign models)", () => {
  it("D: renders the panel default + count; switching to Single reviewer posts a single-role roster", async () => {
    getCouncilRoster.mockResolvedValue({
      reviewer_roster: null,
      panel: ["risk_judge", "policy_judge", "faithfulness_judge", "erasure_judge"],
      // GENERALIST-1: an opt-in lens role outside the panel is selectable as a single reviewer
      selectable: ["risk_judge", "policy_judge", "faithfulness_judge", "erasure_judge", "generalist_reviewer"],
    });
    render(<ProviderSettings agent="clinverdict_default" />);
    await screen.findByTestId("reviewer-mode");
    // panel default reflects the active pack's real reviewer count (4, not the hardcoded 3)
    expect(screen.getByTestId("reviewer-mode-panel")).toHaveTextContent(/Panel · 4/);
    // switch to single → posts a one-role roster for THIS agent (audited)
    fireEvent.click(screen.getByTestId("reviewer-mode-single"));
    await waitFor(() => expect(setCouncilRoster).toHaveBeenCalled());
    const arg = setCouncilRoster.mock.calls.at(-1)[0];
    expect(arg.agent).toBe("clinverdict_default");
    expect(Array.isArray(arg.roster) && arg.roster.length).toBe(1);
    // the single-reviewer picker is offered AND lists the opt-in generalist (selectable, not panel)
    expect(screen.getByTestId("reviewer-single-role")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Generalist reviewer/i })).toBeInTheDocument();
  });

  it("D2: picking the generalist single reviewer posts that one-role roster", async () => {
    getCouncilRoster.mockResolvedValue({
      reviewer_roster: ["faithfulness_judge"],
      panel: ["risk_judge", "policy_judge", "faithfulness_judge", "erasure_judge"],
      selectable: ["risk_judge", "policy_judge", "faithfulness_judge", "erasure_judge", "generalist_reviewer"],
    });
    render(<ProviderSettings agent="clinverdict_default" />);
    await screen.findByTestId("reviewer-single-role");
    fireEvent.change(screen.getByTestId("reviewer-single-role"), { target: { value: "generalist_reviewer" } });
    await waitFor(() => expect(setCouncilRoster).toHaveBeenCalled());
    expect(setCouncilRoster.mock.calls.at(-1)[0].roster).toEqual(["generalist_reviewer"]);
  });

  it("E: panel mode clears the override (roster=null)", async () => {
    getCouncilRoster.mockResolvedValue({
      reviewer_roster: ["faithfulness_judge"],
      panel: ["risk_judge", "policy_judge", "faithfulness_judge"],
    });
    render(<ProviderSettings agent="clinverdict_default" />);
    await screen.findByTestId("reviewer-mode");
    fireEvent.click(screen.getByTestId("reviewer-mode-panel"));
    await waitFor(() => expect(setCouncilRoster).toHaveBeenCalled());
    expect(setCouncilRoster.mock.calls.at(-1)[0].roster).toBeNull();
  });
});

describe("LeftRail — the 'Connect AI' session-menu entry opens/closes the 2-section panel", () => {
  it("C: the session-menu shows 'Connect AI'; clicking it opens the panel; close dismisses it", async () => {
    const { LeftRail } = await import("../panes.jsx");
    const rail = { width: 270, agents: ["ws0_default"], activeAgent: "ws0_default" };
    render(<LeftRail {...rail} />);
    fireEvent.click(screen.getByLabelText("Session menu"));
    const item = screen.getByRole("menuitem", { name: /Connect AI/i });
    expect(item).toBeInTheDocument();
    fireEvent.click(item);
    // the 2-section panel mounts
    expect(await screen.findByTestId("providers-section")).toBeInTheDocument();
    // close dismisses it
    fireEvent.click(screen.getByTestId("provider-settings-close"));
    await waitFor(() => expect(screen.queryByTestId("providers-section")).toBeNull());
  });
});
