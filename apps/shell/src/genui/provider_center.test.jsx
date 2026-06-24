/* provider_center.test.jsx — PROVIDER-CENTER-B: the provider-FIRST config surface (Cline pattern).

   Reshapes Connect AI into a provider-first center: a searchable PROVIDER picker (the broadened set —
   openai · anthropic · azure · gemini · bedrock · openai-compatible), per-provider auth (masked key +
   endpoint where needed), Test & save (reuse configProvider), and a per-CONSUMER picker — each judge
   role binds a {provider, model} from the shared pool (cross-provider per PROVIDER-CENTER-A), while the
   CONVERSATION is Anthropic-only (the assistant runs on the Anthropic Agent SDK; honest inline note).

   A: the provider picker lists the broadened set incl. Gemini / Bedrock / OpenAI-compatible.
   B: selecting a provider + key + Test & save calls configProvider with THAT provider; the endpoint
      field appears for azure / openai_compatible (and only those).
   C: the per-judge picker lists pool entries; choosing {provider, model} for a role calls
      bindModel(id, role); a logprobs:false pool model shows the ⚠ no-logprobs hint.
   D: a MIXED binding renders — risk on one provider, policy on another (the cross-provider council the
      UI now expresses); the conversation picker is Anthropic-scoped with the honest note.
   E: secret hygiene — a typed key is never rendered after save (cleared); no key text in the DOM.
   F: the existing Connect AI grading/assistant surfaces still render (non-destructive reshape). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

const { configProvider, getProviderStatus, getModelCatalog, registerModel, listModels, deleteModel, bindModel } =
  vi.hoisted(() => ({
    configProvider: vi.fn(),
    getProviderStatus: vi.fn(),
    getModelCatalog: vi.fn(),
    registerModel: vi.fn(),
    listModels: vi.fn(),
    deleteModel: vi.fn(),
    bindModel: vi.fn(),
  }));

vi.mock("../bff.js", () => ({
  configProvider, getProviderStatus, getModelCatalog, registerModel, listModels, deleteModel, bindModel,
}));

import ProviderSettings from "./ProviderSettings.jsx";

// a cross-provider pool: openai (logprobs ✓), gemini (logprobs dark), anthropic (logprobs dark)
const POOL = {
  models: [
    {
      id: "grader-gpt4o", provider: "openai", model: "gpt-4o", endpoint: null,
      capabilities: { logprobs: true, context_window: 128000, cost_tier: "mid" },
      last_tested: "2026-06-25T00:00:00+00:00", bound_roles: ["risk_judge"],
    },
    {
      id: "policy-gemini", provider: "gemini", model: "gemini-1.5-pro", endpoint: null,
      capabilities: { logprobs: false, context_window: 1000000, cost_tier: "mid" },
      last_tested: "2026-06-25T00:00:00+00:00", bound_roles: ["policy_judge"],
    },
    {
      id: "chat-sonnet", provider: "anthropic", model: "claude-3-5-sonnet-latest", endpoint: null,
      capabilities: { logprobs: false, context_window: 200000, cost_tier: "mid" },
      last_tested: "2026-06-25T00:00:00+00:00", bound_roles: [],
    },
  ],
};

const CATALOG = {
  providers: {
    openai: [{ model: "gpt-4o", logprobs: true, context_window: 128000, cost_tier: "mid" }],
    anthropic: [{ model: "claude-3-5-sonnet-latest", logprobs: false, context_window: 200000, cost_tier: "mid" }],
    azure: { models: [], note: "Azure is deployment-name based — type your deployment." },
  },
};

beforeEach(() => {
  configProvider.mockReset().mockResolvedValue({ ok: true, plane: "grading", provider: "openai", last_tested: "2026-06-25T00:00:00+00:00" });
  getProviderStatus.mockReset().mockResolvedValue({ planes: {} });
  getModelCatalog.mockReset().mockResolvedValue(CATALOG);
  registerModel.mockReset().mockResolvedValue({});
  listModels.mockReset().mockResolvedValue(POOL);
  deleteModel.mockReset().mockResolvedValue({});
  bindModel.mockReset().mockResolvedValue({ ok: true });
});

describe("PROVIDER-CENTER-B — the provider-first surface", () => {
  it("A: the provider picker lists the broadened set incl. Gemini / Bedrock / OpenAI-compatible", async () => {
    render(<ProviderSettings />);
    const picker = await screen.findByTestId("provider-picker");
    // the broadened provider set is selectable
    for (const p of ["openai", "anthropic", "azure", "gemini", "bedrock", "openai_compatible"]) {
      expect(within(picker).getByRole("option", { name: new RegExp(p.replace("_", "[ _-]?"), "i") })).toBeInTheDocument();
    }
  });

  it("B: selecting a provider + key + Test & save calls configProvider with that provider; endpoint field for azure/openai_compatible only", async () => {
    render(<ProviderSettings />);
    const picker = await screen.findByTestId("provider-picker");

    // openai: no endpoint field
    fireEvent.change(picker, { target: { value: "openai" } });
    expect(screen.queryByTestId("provider-endpoint")).toBeNull();

    // azure: endpoint field appears
    fireEvent.change(picker, { target: { value: "azure" } });
    expect(await screen.findByTestId("provider-endpoint")).toBeInTheDocument();

    // openai_compatible: endpoint field appears
    fireEvent.change(picker, { target: { value: "openai_compatible" } });
    expect(await screen.findByTestId("provider-endpoint")).toBeInTheDocument();

    // back to openai, key + Test & save → configProvider with provider=openai
    fireEvent.change(picker, { target: { value: "openai" } });
    const keyInput = screen.getByTestId("provider-key");
    expect(keyInput).toHaveAttribute("type", "password");
    fireEvent.change(keyInput, { target: { value: "sk-openai-1" } });
    fireEvent.click(screen.getByTestId("provider-test-save"));
    await waitFor(() =>
      expect(configProvider).toHaveBeenCalledWith(
        expect.objectContaining({ provider: "openai", api_key: "sk-openai-1" }),
      ),
    );
  });

  it("C: the per-judge picker lists pool entries; choosing one + Bind calls bindModel(id, role); a logprobs:false model shows the ⚠ hint", async () => {
    render(<ProviderSettings />);
    const sel = await screen.findByTestId("judge-bind-select-risk_judge");
    // pool entries (with provider) are options
    expect(within(sel).getByRole("option", { name: /grader-gpt4o/i })).toBeInTheDocument();
    expect(within(sel).getByRole("option", { name: /policy-gemini/i })).toBeInTheDocument();
    // choosing the gemini (logprobs:false) entry surfaces the ⚠ no-logprobs hint at pick time
    fireEvent.change(sel, { target: { value: "policy-gemini" } });
    expect(await screen.findByTestId("judge-bind-logprobs-hint-risk_judge")).toHaveTextContent(/no logprobs|confidence dark/i);
    fireEvent.click(screen.getByTestId("judge-bind-submit-risk_judge"));
    await waitFor(() => expect(bindModel).toHaveBeenCalledWith("policy-gemini", "risk_judge"));
  });

  it("D: a MIXED binding renders (risk→openai, policy→gemini); the conversation picker is Anthropic-scoped with the honest note", async () => {
    render(<ProviderSettings />);
    // the pool reflects the cross-provider council: risk bound on openai, policy bound on gemini
    const risk = await screen.findByTestId("judge-bind-row-risk_judge");
    const policy = await screen.findByTestId("judge-bind-row-policy_judge");
    expect(within(risk).getByText(/openai/i)).toBeInTheDocument();
    expect(within(policy).getByText(/gemini/i)).toBeInTheDocument();

    // the conversation picker is Anthropic-only: it lists the anthropic pool entry, NOT the openai/gemini ones
    const conv = await screen.findByTestId("conversation-model-select");
    expect(within(conv).getByRole("option", { name: /chat-sonnet/i })).toBeInTheDocument();
    expect(within(conv).queryByRole("option", { name: /grader-gpt4o/i })).toBeNull();
    expect(within(conv).queryByRole("option", { name: /policy-gemini/i })).toBeNull();
    // the honest inline note: chat is Anthropic-only today
    expect(screen.getByTestId("conversation-anthropic-note")).toHaveTextContent(/anthropic/i);
  });

  it("E: secret hygiene — a typed provider key is never rendered after save (cleared); no key text in the DOM", async () => {
    const { container } = render(<ProviderSettings />);
    const picker = await screen.findByTestId("provider-picker");
    fireEvent.change(picker, { target: { value: "openai" } });
    const keyInput = screen.getByTestId("provider-key");
    fireEvent.change(keyInput, { target: { value: "sk-super-secret-xyz" } });
    // non-vacuous: the value IS in the field before save
    expect(keyInput.value).toBe("sk-super-secret-xyz");
    fireEvent.click(screen.getByTestId("provider-test-save"));
    await waitFor(() => expect(configProvider).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("provider-key").value).toBe(""));
    expect(container.innerHTML).not.toContain("sk-super-secret-xyz");
  });

  it("F: the existing grading + assistant + model-pool surfaces still render (non-destructive reshape)", async () => {
    render(<ProviderSettings />);
    expect(await screen.findByText("Grading engine")).toBeInTheDocument();
    expect(screen.getByText("Authoring assistant")).toBeInTheDocument();
    expect(screen.getByTestId("model-registry-section")).toBeInTheDocument();
  });
});
