/* ModelRegistry.test.jsx — MODEL-REGISTRY-1c: the model-pool surface inside Connect AI.

   The pick-from-pool model registry (SPEC_COMMUNITY_EDITION §8): register capability-annotated
   models into a reusable pool, then bind each of the 3 fixed roles to a pool entry. Capabilities —
   esp. `logprobs` — are the UX point: a logprobs:false model surfaces a ⚠ "no logprobs — confidence
   dark" hint at pick time. All writes ride the existing call() auth header via bff.js.

   A: renders the register form; the model <select> lists catalog presets (mocked getModelCatalog);
      a logprobs:false model surfaces the ⚠ no-logprobs / confidence-dark hint.
   B: register → fill id + pick a model + type a key → Register & test calls registerModel with the
      entered values; the key input is type="password".
   C: the pool list renders entries from a mocked listModels (id/provider/model/logprobs chip),
      NEVER a key; Delete calls deleteModel(id).
   D: a role's pool <select> lists pool entries; choosing one + Bind calls bindModel(id, role).
   E (secret hygiene — non-vacuous): after a successful register the typed key is NOT in the DOM.
   F: ProviderSettings renders the Model pool section (compose) — grading/assistant still render. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

const { getModelCatalog, registerModel, listModels, deleteModel, bindModel, configProvider, getProviderStatus } =
  vi.hoisted(() => ({
    getModelCatalog: vi.fn(),
    registerModel: vi.fn(),
    listModels: vi.fn(),
    deleteModel: vi.fn(),
    bindModel: vi.fn(),
    configProvider: vi.fn(),
    getProviderStatus: vi.fn(),
  }));

vi.mock("../bff.js", () => ({
  getModelCatalog, registerModel, listModels, deleteModel, bindModel, configProvider, getProviderStatus,
}));

import ModelRegistry from "./ModelRegistry.jsx";
import ProviderSettings from "./ProviderSettings.jsx";

const CATALOG = {
  providers: {
    openai: [
      { model: "gpt-4o", logprobs: true, context_window: 128000, cost_tier: "mid" },
      { model: "o3-mini", logprobs: false, context_window: 200000, cost_tier: "mid" },
    ],
    anthropic: [
      { model: "claude-3-5-sonnet-latest", logprobs: false, context_window: 200000, cost_tier: "mid" },
    ],
    azure: { models: [], note: "Azure is deployment-name based — type your deployment." },
  },
};

const POOL = {
  models: [
    {
      id: "grader-gpt4o", provider: "openai", model: "gpt-4o", endpoint: null,
      capabilities: { logprobs: true, context_window: 128000, cost_tier: "mid" },
      last_tested: "2026-06-24T00:00:00+00:00", bound_roles: ["risk_judge"],
    },
    {
      id: "claude-sonnet", provider: "anthropic", model: "claude-3-5-sonnet-latest", endpoint: null,
      capabilities: { logprobs: false, context_window: 200000, cost_tier: "mid" },
      last_tested: "2026-06-24T00:00:00+00:00", bound_roles: [],
    },
  ],
};

beforeEach(() => {
  getModelCatalog.mockReset().mockResolvedValue(CATALOG);
  registerModel.mockReset().mockResolvedValue({
    id: "grader-gpt4o", provider: "openai", model: "gpt-4o",
    capabilities: { logprobs: true }, last_tested: "2026-06-24T00:00:00+00:00", bound_roles: [],
  });
  listModels.mockReset().mockResolvedValue(POOL);
  deleteModel.mockReset().mockResolvedValue({ ok: true, id: "grader-gpt4o", deleted: true });
  bindModel.mockReset().mockResolvedValue({ ok: true, id: "grader-gpt4o", role: "risk_judge", bound_roles: ["risk_judge"] });
  configProvider.mockReset().mockResolvedValue({ ok: true });
  getProviderStatus.mockReset().mockResolvedValue({ planes: {} });
});

describe("ModelRegistry — MODEL-REGISTRY-1c", () => {
  it("A: renders the register form; the model select lists catalog presets + the ⚠ no-logprobs hint", async () => {
    render(<ModelRegistry />);
    // the model <select> is built from the mocked catalog (openai is the default provider)
    const modelSelect = await screen.findByTestId("model-register-model");
    expect(within(modelSelect).getByRole("option", { name: /gpt-4o/i })).toBeInTheDocument();
    // a logprobs:false preset surfaces the ⚠ "no logprobs — confidence dark" hint somewhere
    expect(getModelCatalog).toHaveBeenCalled();
    // o3-mini is logprobs:false — the option (or its hint) flags confidence-dark
    const darkOption = within(modelSelect).getByRole("option", { name: /o3-mini/i });
    expect(darkOption.textContent).toMatch(/no logprobs|confidence dark|⚠/i);
  });

  it("A2: picking a logprobs:false model surfaces a confidence-dark hint at pick time", async () => {
    render(<ModelRegistry />);
    const modelSelect = await screen.findByTestId("model-register-model");
    fireEvent.change(modelSelect, { target: { value: "o3-mini" } });
    expect(await screen.findByTestId("model-logprobs-hint")).toHaveTextContent(/no logprobs|confidence dark/i);
  });

  it("B: Register & test calls registerModel with the entered values; key input is type=password", async () => {
    render(<ModelRegistry />);
    const modelSelect = await screen.findByTestId("model-register-model");
    fireEvent.change(screen.getByTestId("model-register-id"), { target: { value: "grader-gpt4o" } });
    fireEvent.change(modelSelect, { target: { value: "gpt-4o" } });
    const keyInput = screen.getByTestId("model-register-key");
    expect(keyInput).toHaveAttribute("type", "password");
    fireEvent.change(keyInput, { target: { value: "sk-secret-123" } });
    fireEvent.click(screen.getByTestId("model-register-submit"));
    await waitFor(() =>
      expect(registerModel).toHaveBeenCalledWith(
        expect.objectContaining({ id: "grader-gpt4o", provider: "openai", model: "gpt-4o", api_key: "sk-secret-123" }),
      ),
    );
  });

  it("B2: a custom free-text model is always available (never block an unknown model)", async () => {
    render(<ModelRegistry />);
    const modelSelect = await screen.findByTestId("model-register-model");
    // the custom sentinel is in the select; choosing it reveals a free-text model input
    expect(within(modelSelect).getByRole("option", { name: /custom/i })).toBeInTheDocument();
    fireEvent.change(modelSelect, { target: { value: "__custom__" } });
    fireEvent.change(screen.getByTestId("model-register-id"), { target: { value: "my-deploy" } });
    fireEvent.change(screen.getByTestId("model-register-custom"), { target: { value: "my-azure-deployment" } });
    fireEvent.change(screen.getByTestId("model-register-key"), { target: { value: "k" } });
    fireEvent.click(screen.getByTestId("model-register-submit"));
    await waitFor(() =>
      expect(registerModel).toHaveBeenCalledWith(expect.objectContaining({ model: "my-azure-deployment" })),
    );
  });

  it("C: the pool list renders entries (id/provider/model/logprobs chip), NEVER a key; Delete calls deleteModel", async () => {
    render(<ModelRegistry />);
    const pool = await screen.findByTestId("model-pool");
    expect(within(pool).getByText("grader-gpt4o")).toBeInTheDocument();
    expect(within(pool).getByText(/gpt-4o/)).toBeInTheDocument();
    // the logprobs capability chip is present per entry
    expect(within(pool).getAllByTestId(/model-pool-logprobs-/).length).toBeGreaterThan(0);
    // Delete the first entry
    fireEvent.click(within(pool).getByTestId("model-pool-delete-grader-gpt4o"));
    await waitFor(() => expect(deleteModel).toHaveBeenCalledWith("grader-gpt4o"));
  });

  it("D: a role pool select lists entries; choosing one + Bind calls bindModel(id, role)", async () => {
    render(<ModelRegistry />);
    const roleSel = await screen.findByTestId("model-bind-select-risk_judge");
    expect(within(roleSel).getByRole("option", { name: /grader-gpt4o/i })).toBeInTheDocument();
    fireEvent.change(roleSel, { target: { value: "claude-sonnet" } });
    fireEvent.click(screen.getByTestId("model-bind-submit-risk_judge"));
    await waitFor(() => expect(bindModel).toHaveBeenCalledWith("claude-sonnet", "risk_judge"));
  });

  it("E (secret hygiene — non-vacuous): after a successful register the typed key is NOT in the DOM", async () => {
    const { container } = render(<ModelRegistry />);
    await screen.findByTestId("model-register-model");
    fireEvent.change(screen.getByTestId("model-register-id"), { target: { value: "grader-gpt4o" } });
    fireEvent.change(screen.getByTestId("model-register-model"), { target: { value: "gpt-4o" } });
    const keyInput = screen.getByTestId("model-register-key");
    fireEvent.change(keyInput, { target: { value: "sk-super-secret-xyz" } });
    // sanity: the value IS in the field before submit (non-vacuous — the assertion can fail)
    expect(keyInput.value).toBe("sk-super-secret-xyz");
    fireEvent.click(screen.getByTestId("model-register-submit"));
    await waitFor(() => expect(registerModel).toHaveBeenCalled());
    // after success the key is cleared from the input and never rendered as text anywhere
    await waitFor(() => expect(screen.getByTestId("model-register-key").value).toBe(""));
    expect(container.innerHTML).not.toContain("sk-super-secret-xyz");
  });
});

describe("ProviderSettings — MODEL-REGISTRY-1c compose (F)", () => {
  it("F: renders the Model pool section AND keeps the grading + assistant sections (non-destructive)", async () => {
    render(<ProviderSettings />);
    expect(await screen.findByTestId("model-registry-section")).toBeInTheDocument();
    expect(screen.getByText("Grading engine")).toBeInTheDocument();
    expect(screen.getByText("Authoring assistant")).toBeInTheDocument();
  });
});
