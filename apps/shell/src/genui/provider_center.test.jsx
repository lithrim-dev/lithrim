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

const { configProvider, getProviderStatus, getModelCatalog, bindRole, getRoleBindings,
  hasStoredToken, logout, signIn } = vi.hoisted(() => ({
  configProvider: vi.fn(),
  getProviderStatus: vi.fn(),
  getModelCatalog: vi.fn(),
  bindRole: vi.fn(),
  getRoleBindings: vi.fn(),
  // UI-LOGIN-1 / SESSION-MENU-1: LeftRail reads these for the session-menu affordance.
  hasStoredToken: vi.fn(),
  logout: vi.fn(),
  signIn: vi.fn(),
}));

vi.mock("../bff.js", () => ({
  configProvider, getProviderStatus, getModelCatalog, bindRole, getRoleBindings,
  hasStoredToken, logout, signIn,
}));
// the LeftRail lives in panes.jsx (one dir up from genui/); mock its bff path too.
vi.mock("../../bff.js", () => ({
  configProvider, getProviderStatus, getModelCatalog, bindRole, getRoleBindings,
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

  it("B: the connected-providers list renders from getRoleBindings.connected_providers", async () => {
    render(<ProviderSettings />);
    expect(await screen.findByTestId("providers-connected-row-openai")).toBeInTheDocument();
    expect(screen.getByTestId("providers-connected-row-gemini")).toBeInTheDocument();
    // a no-logprobs provider carries the ⚠ hint in its row
    expect(screen.getByTestId("providers-connected-row-gemini")).toHaveTextContent(/no logprobs/i);
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
