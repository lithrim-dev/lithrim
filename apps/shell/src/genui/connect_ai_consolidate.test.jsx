/* connect_ai_consolidate.test.jsx — CONNECT-AI-CONSOLIDATE-1: the 2-section Connect AI panel.

   The 5-section panel (ProviderPicker + Grading Simple/Advanced + ModelRegistry + ConsumerBind +
   Authoring assistant) collapses to TWO:
     (1) Providers — the ONLY place a key is entered (the broadened set; endpoint only for
         azure/openai_compatible). configProvider stores the provider key (no model).
     (2) Assign models — FOUR rows (risk_judge, policy_judge, faithfulness_judge, chat_assistant);
         each {provider · model} pick → bindRole(role, provider, model); the chat_assistant row is
         REQUIRED and CROSS-PROVIDER; a setup-complete gate requires all 3 judges AND chat.

   A: the panel renders EXACTLY the two sections; the retired sections/components are gone.
   B: Providers — pick provider + key + save → configProvider with that provider (no model); endpoint
      field for azure/openai_compatible only; the key clears on success (secret hygiene).
   C: Assign models — FOUR rows incl. chat_assistant; choosing {provider, model} → bindRole(...).
   D: the compulsory-chat gate is NON-VACUOUS — 3 judges bound but chat unbound → "not ready"; once
      chat is bound → ready (assert BOTH).
   E: the chat row is CROSS-PROVIDER (lists non-anthropic options); the old "Anthropic-only" note is gone.
   F: a no-logprobs provider/model shows the ⚠ hint; "use one model for all judges" binds the 3. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

const { configProvider, getProviderStatus, getModelCatalog, bindRole, getRoleBindings, getCouncilRoster, setCouncilRoster } =
  vi.hoisted(() => ({
    configProvider: vi.fn(),
    getProviderStatus: vi.fn(),
    getModelCatalog: vi.fn(),
    bindRole: vi.fn(),
    getRoleBindings: vi.fn(),
    getCouncilRoster: vi.fn().mockResolvedValue({ panel: [], reviewer_roster: null }),
    setCouncilRoster: vi.fn().mockResolvedValue({ status: "ok" }),
  }));

vi.mock("../bff.js", () => ({ configProvider, getProviderStatus, getModelCatalog, bindRole, getRoleBindings, getCouncilRoster, setCouncilRoster }));

import ProviderSettings from "./ProviderSettings.jsx";

const CATALOG = {
  providers: {
    openai: [{ model: "gpt-4o", logprobs: true, context_window: 128000, cost_tier: "mid" }],
    anthropic: [{ model: "claude-3-5-sonnet-latest", logprobs: false, context_window: 200000, cost_tier: "mid" }],
    gemini: [{ model: "gemini-1.5-pro", logprobs: false, context_window: 1000000, cost_tier: "mid" }],
    azure: { models: [], note: "Azure is deployment-name based — type your deployment." },
  },
};

// the connected-provider list + a no role bound (the unconfigured baseline)
const UNBOUND = {
  roles: {
    risk_judge: null, policy_judge: null, faithfulness_judge: null, chat_assistant: null,
  },
  connected_providers: ["openai", "anthropic", "gemini"],
};
// 3 judges bound, chat unbound (the compulsory-chat NOT-ready state)
const JUDGES_ONLY = {
  roles: {
    risk_judge: { provider: "openai", model: "gpt-4o" },
    policy_judge: { provider: "gemini", model: "gemini-1.5-pro" },
    faithfulness_judge: { provider: "openai", model: "gpt-4o" },
    chat_assistant: null,
  },
  connected_providers: ["openai", "anthropic", "gemini"],
};
// all 4 bound (ready)
const ALL_FOUR = {
  roles: {
    risk_judge: { provider: "openai", model: "gpt-4o" },
    policy_judge: { provider: "gemini", model: "gemini-1.5-pro" },
    faithfulness_judge: { provider: "openai", model: "gpt-4o" },
    chat_assistant: { provider: "openai", model: "gpt-4o" },
  },
  connected_providers: ["openai", "anthropic", "gemini"],
};

beforeEach(() => {
  configProvider.mockReset().mockResolvedValue({ ok: true, plane: "grading", provider: "openai", last_tested: "2026-06-25T00:00:00+00:00" });
  getProviderStatus.mockReset().mockResolvedValue({ planes: {} });
  getModelCatalog.mockReset().mockResolvedValue(CATALOG);
  bindRole.mockReset().mockResolvedValue({ ok: true });
  getRoleBindings.mockReset().mockResolvedValue(UNBOUND);
});

describe("CONNECT-AI-CONSOLIDATE-1 — the 2-section panel", () => {
  it("A: renders EXACTLY the two sections; the retired sections/components are gone", async () => {
    render(<ProviderSettings />);
    expect(await screen.findByTestId("providers-section")).toBeInTheDocument();
    expect(screen.getByTestId("assign-models-section")).toBeInTheDocument();
    // retired components/sections — gone
    expect(screen.queryByTestId("provider-picker-section")).toBeNull();
    expect(screen.queryByTestId("model-registry-section")).toBeNull();
    expect(screen.queryByTestId("consumer-bind-section")).toBeNull();
    expect(screen.queryByTestId("grading-simple-toggle")).toBeNull();
    expect(screen.queryByTestId("assistant-test-save")).toBeNull();
    // the old per-consumer judge-bind UI (ConsumerBind) is gone — the new rows are role-bind-row-*
    expect(screen.queryByTestId("judge-bind-select-risk_judge")).toBeNull();
  });

  it("B: Providers — pick provider + key + save → configProvider (no model); endpoint for azure/openai_compatible only; key clears", async () => {
    const { container } = render(<ProviderSettings />);
    const picker = await screen.findByTestId("providers-provider");

    // openai → no endpoint field
    fireEvent.change(picker, { target: { value: "openai" } });
    expect(screen.queryByTestId("providers-endpoint")).toBeNull();
    // azure → endpoint field
    fireEvent.change(picker, { target: { value: "azure" } });
    expect(await screen.findByTestId("providers-endpoint")).toBeInTheDocument();
    // openai_compatible → endpoint field
    fireEvent.change(picker, { target: { value: "openai_compatible" } });
    expect(await screen.findByTestId("providers-endpoint")).toBeInTheDocument();

    // back to openai, type the key, save → configProvider with provider=openai, NO model field here
    fireEvent.change(picker, { target: { value: "openai" } });
    const keyInput = screen.getByTestId("providers-key");
    expect(keyInput).toHaveAttribute("type", "password");
    fireEvent.change(keyInput, { target: { value: "sk-providers-secret-1" } });
    expect(keyInput.value).toBe("sk-providers-secret-1");  // non-vacuous before save
    fireEvent.click(screen.getByTestId("providers-save"));
    await waitFor(() =>
      expect(configProvider).toHaveBeenCalledWith(
        expect.objectContaining({ provider: "openai", api_key: "sk-providers-secret-1" }),
      ),
    );
    // there is no model in the providers form call
    expect(configProvider.mock.calls[0][0].model).toBeUndefined();
    // secret hygiene — the key clears on success + is absent from the DOM
    await waitFor(() => expect(screen.getByTestId("providers-key").value).toBe(""));
    expect(container.innerHTML).not.toContain("sk-providers-secret-1");
  });

  // Theme B/D: a failed save reads as an ERROR (red --accent), not a WARNING (amber), and shows a
  // calm friendlyError line — never the raw HTTP/stack.
  it("B-err: a failed key save shows the error tone (red, not amber) + a calm reason", async () => {
    configProvider.mockReset().mockRejectedValue(new Error("POST /v1/provider/config → 401: unauthorized"));
    render(<ProviderSettings />);
    const keyInput = await screen.findByTestId("providers-key");
    fireEvent.change(keyInput, { target: { value: "sk-bad" } });
    fireEvent.click(screen.getByTestId("providers-save"));

    const msg = await screen.findByTestId("providers-save-msg");
    expect(msg).toHaveStyle({ color: "var(--accent)" }); // failure = red, NOT amber (--amber)
    expect(msg.textContent).not.toMatch(/401|provider\/config|→/); // no raw HTTP leak
  });

  it("C: Assign models — FOUR rows incl. chat_assistant; choosing {provider, model} → bindRole(role, provider, model)", async () => {
    render(<ProviderSettings />);
    for (const role of ["risk_judge", "policy_judge", "faithfulness_judge", "chat_assistant"]) {
      expect(await screen.findByTestId(`role-bind-row-${role}`)).toBeInTheDocument();
    }
    // CONNECT-AI-AZURE-1: pick the provider, then pick/type the model → bindRole
    fireEvent.change(screen.getByTestId("role-bind-provider-risk_judge"), { target: { value: "openai" } });
    fireEvent.change(screen.getByTestId("role-bind-model-risk_judge"), { target: { value: "gpt-4o" } });
    fireEvent.click(screen.getByTestId("role-bind-submit-risk_judge"));
    await waitFor(() => expect(bindRole).toHaveBeenCalledWith({ role: "risk_judge", provider: "openai", model: "gpt-4o" }));
  });

  it("D: the compulsory-chat gate is NON-VACUOUS — 3 judges + chat unbound → not ready; all 4 → ready", async () => {
    // 3 judges bound, chat unbound → NOT ready
    getRoleBindings.mockResolvedValue(JUDGES_ONLY);
    const { unmount } = render(<ProviderSettings />);
    const notReady = await screen.findByTestId("setup-complete-status");
    expect(notReady).toHaveTextContent(/chat assistant still needs a model|not ready|needs a model/i);
    expect(notReady).not.toHaveTextContent(/ready — 4 of 4/i);
    unmount();

    // all 4 bound → READY
    getRoleBindings.mockResolvedValue(ALL_FOUR);
    render(<ProviderSettings />);
    const ready = await screen.findByTestId("setup-complete-status");
    expect(ready).toHaveTextContent(/ready — 4 of 4|ready/i);
    expect(ready).not.toHaveTextContent(/still needs/i);
  });

  it("E: the chat row is CROSS-PROVIDER (lists non-anthropic providers); the old Anthropic-only note is gone", async () => {
    render(<ProviderSettings />);
    // CONNECT-AI-AZURE-1: cross-provider = the chat provider <select> lists openai AND gemini
    const chatProv = await screen.findByTestId("role-bind-provider-chat_assistant");
    expect(within(chatProv).getByRole("option", { name: "openai" })).toBeInTheDocument();
    expect(within(chatProv).getByRole("option", { name: "gemini" })).toBeInTheDocument();
    // picking openai surfaces its preset model (gpt-4o) in the chat row's datalist
    fireEvent.change(chatProv, { target: { value: "openai" } });
    const chatList = screen.getByTestId("role-bind-modellist-chat_assistant");
    expect(chatList.querySelector('option[value="gpt-4o"]')).not.toBeNull();
    // the chat row is labelled required
    expect(screen.getByTestId("role-bind-row-chat_assistant")).toHaveTextContent(/required/i);
    // the old Anthropic-only deferral note is gone
    expect(screen.queryByTestId("conversation-anthropic-note")).toBeNull();
  });

  it("F: a no-logprobs model shows the ⚠ hint; 'use one model for all judges' binds the 3 judge rows", async () => {
    render(<ProviderSettings />);
    // pick a gemini (logprobs:false) model for policy_judge → the ⚠ hint
    fireEvent.change(await screen.findByTestId("role-bind-provider-policy_judge"), { target: { value: "gemini" } });
    fireEvent.change(screen.getByTestId("role-bind-model-policy_judge"), { target: { value: "gemini-1.5-pro" } });
    expect(await screen.findByTestId("role-bind-logprobs-hint-policy_judge")).toHaveTextContent(/doesn't report a confidence signal/i);

    // the "use one model for all judges" shortcut → binds risk + policy + faithfulness (NOT chat)
    fireEvent.change(screen.getByTestId("all-judges-provider-*"), { target: { value: "openai" } });
    fireEvent.change(screen.getByTestId("all-judges-model-*"), { target: { value: "gpt-4o" } });
    fireEvent.click(screen.getByTestId("all-judges-submit"));
    await waitFor(() => {
      expect(bindRole).toHaveBeenCalledWith({ role: "risk_judge", provider: "openai", model: "gpt-4o" });
      expect(bindRole).toHaveBeenCalledWith({ role: "policy_judge", provider: "openai", model: "gpt-4o" });
      expect(bindRole).toHaveBeenCalledWith({ role: "faithfulness_judge", provider: "openai", model: "gpt-4o" });
    });
    expect(bindRole).not.toHaveBeenCalledWith(expect.objectContaining({ role: "chat_assistant" }));
  });
});
