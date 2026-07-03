/* connect_ai_azure.test.jsx — CONNECT-AI-AZURE-1: the UI-only multi-provider Azure flow.

   Two blockers fixed (both RED before the fix):
     1. The Assign-models picker goes EMPTY for Azure (catalog {models:[], note}) — a connected
        provider with no presets contributed ZERO options to the old <select>, so an Azure
        deployment could not be picked. The fix: a provider <select> + a model <input list=datalist>
        that offers presets AND accepts FREE TEXT, so an Azure deployment can be TYPED and bound.
     2. ProvidersSection drops api_version for Azure. The fix: an OPTIONAL "API version" input for
        azure (only), passed to configProvider.

   A (the EMPTY-picker RED): azure connected, catalog {models:[]} → TYPE a deployment in the
      risk_judge model input + Assign → bindRole({role:"risk_judge", provider:"azure", model:<typed>}).
   B: openai presets still offered (datalist) + free-text still allowed (a typed custom model binds).
   C: the ⚠ no-logprobs hint + the compulsory-chat gate still assert (non-vacuous, both states).
   D: ProvidersSection — azure shows the api-version input; saving azure calls configProvider with
      api_version; non-azure hides it; the typed key clears on success (hygiene). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

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
    gemini: [{ model: "gemini-1.5-pro", logprobs: false, context_window: 1000000, cost_tier: "mid" }],
    azure: { models: [], note: "Azure is deployment-name based — type your deployment." },
  },
};

// azure IS connected, but its catalog has zero presets (the EMPTY-picker condition)
const AZURE_CONNECTED = {
  roles: { risk_judge: null, policy_judge: null, faithfulness_judge: null, chat_assistant: null },
  connected_providers: ["azure", "openai", "gemini"],
};
const ALL_FOUR = {
  roles: {
    risk_judge: { provider: "azure", model: "my-gpt-deploy" },
    policy_judge: { provider: "azure", model: "my-mistral-deploy" },
    faithfulness_judge: { provider: "azure", model: "my-llama-deploy" },
    chat_assistant: { provider: "azure", model: "my-chat-deploy" },
  },
  connected_providers: ["azure", "openai", "gemini"],
};

beforeEach(() => {
  configProvider.mockReset().mockResolvedValue({ ok: true, plane: "grading", provider: "azure", last_tested: "2026-06-25T00:00:00+00:00" });
  getProviderStatus.mockReset().mockResolvedValue({ planes: {} });
  getModelCatalog.mockReset().mockResolvedValue(CATALOG);
  bindRole.mockReset().mockResolvedValue({ ok: true });
  getRoleBindings.mockReset().mockResolvedValue(AZURE_CONNECTED);
});

describe("CONNECT-AI-AZURE-1 — free-text deployment + the api-version field", () => {
  it("A (the EMPTY-picker RED): azure connected with no presets — TYPE a deployment + Assign → bindRole azure", async () => {
    render(<ProviderSettings />);
    // pick azure as the provider for the risk_judge row
    const provSel = await screen.findByTestId("role-bind-provider-risk_judge");
    fireEvent.change(provSel, { target: { value: "azure" } });
    // azure has NO presets — but the model input accepts FREE TEXT (a typed deployment name)
    const modelInput = screen.getByTestId("role-bind-model-risk_judge");
    fireEvent.change(modelInput, { target: { value: "my-gpt-deploy" } });
    fireEvent.click(screen.getByTestId("role-bind-submit-risk_judge"));
    await waitFor(() =>
      expect(bindRole).toHaveBeenCalledWith({ role: "risk_judge", provider: "azure", model: "my-gpt-deploy" }),
    );
  });

  it("B: openai presets offered via datalist + free-text custom model still binds", async () => {
    render(<ProviderSettings />);
    const provSel = await screen.findByTestId("role-bind-provider-policy_judge");
    fireEvent.change(provSel, { target: { value: "openai" } });
    // the datalist exists for openai presets (gpt-4o is an option)
    const list = screen.getByTestId("role-bind-modellist-policy_judge");
    expect(list.querySelector('option[value="gpt-4o"]')).not.toBeNull();
    // a typed CUSTOM (non-preset) model still binds (free text)
    const modelInput = screen.getByTestId("role-bind-model-policy_judge");
    fireEvent.change(modelInput, { target: { value: "gpt-4o-custom-ft" } });
    fireEvent.click(screen.getByTestId("role-bind-submit-policy_judge"));
    await waitFor(() =>
      expect(bindRole).toHaveBeenCalledWith({ role: "policy_judge", provider: "openai", model: "gpt-4o-custom-ft" }),
    );
  });

  it("C: the ⚠ no-logprobs hint shows for a gemini model; the compulsory-chat gate is non-vacuous", async () => {
    // gemini (logprobs:false) → the ⚠ hint at pick time
    render(<ProviderSettings />);
    const provSel = await screen.findByTestId("role-bind-provider-faithfulness_judge");
    fireEvent.change(provSel, { target: { value: "gemini" } });
    fireEvent.change(screen.getByTestId("role-bind-model-faithfulness_judge"), { target: { value: "gemini-1.5-pro" } });
    expect(await screen.findByTestId("role-bind-logprobs-hint-faithfulness_judge")).toHaveTextContent(/doesn't report a confidence signal/i);
    // gate: azure-connected but NOTHING bound → not ready
    const notReady = screen.getByTestId("setup-complete-status");
    expect(notReady).toHaveTextContent(/needs a model|not ready|still needs/i);
  });

  it("C2: all 4 azure roles bound → the gate reports ready", async () => {
    getRoleBindings.mockResolvedValue(ALL_FOUR);
    render(<ProviderSettings />);
    const ready = await screen.findByTestId("setup-complete-status");
    expect(ready).toHaveTextContent(/ready — 4 of 4|ready/i);
    expect(ready).not.toHaveTextContent(/still needs/i);
  });

  it("E (PREFILL): an already-assigned role pre-fills its provider + model controls (not empty)", async () => {
    // CONNECT-AI-PREFILL-1: a configured role must show its saved binding IN the editable controls,
    // not an empty field next to a ✓ — else a fully-configured panel reads as unconfigured.
    getRoleBindings.mockResolvedValue(ALL_FOUR);
    render(<ProviderSettings />);
    await screen.findByTestId("role-bind-assigned-risk_judge"); // bindings have loaded
    expect(screen.getByTestId("role-bind-provider-risk_judge").value).toBe("azure");
    expect(screen.getByTestId("role-bind-model-risk_judge").value).toBe("my-gpt-deploy");
    expect(screen.getByTestId("role-bind-provider-faithfulness_judge").value).toBe("azure");
    expect(screen.getByTestId("role-bind-model-faithfulness_judge").value).toBe("my-llama-deploy");
  });

  it("E2 (PREFILL non-vacuous): an UNassigned role leaves its controls empty", async () => {
    // only risk_judge is bound; the rest stay empty (the prefill must not seed unbound rows)
    getRoleBindings.mockResolvedValue({
      roles: { risk_judge: { provider: "azure", model: "my-gpt-deploy" }, policy_judge: null, faithfulness_judge: null, chat_assistant: null },
      connected_providers: ["azure", "openai", "gemini"],
    });
    render(<ProviderSettings />);
    await screen.findByTestId("role-bind-assigned-risk_judge");
    expect(screen.getByTestId("role-bind-provider-risk_judge").value).toBe("azure");
    expect(screen.getByTestId("role-bind-provider-policy_judge").value).toBe("");
    expect(screen.getByTestId("role-bind-model-policy_judge").value).toBe("");
  });

  it("D: ProvidersSection — azure shows the api-version input; save passes api_version; non-azure hides it; key clears", async () => {
    const { container } = render(<ProviderSettings />);
    const picker = await screen.findByTestId("providers-provider");

    // openai → no api-version field
    fireEvent.change(picker, { target: { value: "openai" } });
    expect(screen.queryByTestId("providers-api-version")).toBeNull();

    // azure → the endpoint + the OPTIONAL api-version field appear
    fireEvent.change(picker, { target: { value: "azure" } });
    expect(await screen.findByTestId("providers-endpoint")).toBeInTheDocument();
    const apiVer = screen.getByTestId("providers-api-version");
    expect(apiVer).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("providers-endpoint"), { target: { value: "https://my.openai.azure.com/" } });
    fireEvent.change(apiVer, { target: { value: "2024-12-01-preview" } });
    const keyInput = screen.getByTestId("providers-key");
    fireEvent.change(keyInput, { target: { value: "az-providers-secret-1" } });
    fireEvent.click(screen.getByTestId("providers-save"));

    await waitFor(() =>
      expect(configProvider).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "azure",
          api_key: "az-providers-secret-1",
          endpoint: "https://my.openai.azure.com/",
          api_version: "2024-12-01-preview",
        }),
      ),
    );
    // secret hygiene — the key clears on success + is absent from the DOM
    await waitFor(() => expect(screen.getByTestId("providers-key").value).toBe(""));
    expect(container.innerHTML).not.toContain("az-providers-secret-1");
  });
});
