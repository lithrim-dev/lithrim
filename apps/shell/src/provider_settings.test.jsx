/* provider_settings.test.jsx — CE-PROVIDER-UI (Build B): the in-app "Connect AI" surface.

   A capability-oriented provider-connect panel — "Grading engine" (required) + "Authoring
   assistant" (optional) — reusing the masked-password + test-then-save idiom of ConnectorForm.
   It writes via configProvider (POST /v1/provider/config) and reads via getProviderStatus
   (GET /v1/provider/status); both ride the existing call() auth header (bff.js).

   A: ProviderSettings renders both slots (grading required, assistant optional).
   B: entering a key + Test calls configProvider with the entered value (masked password input).
   C: a passing status renders the connected badge (getProviderStatus mocked).
   D: the rail session-menu shows "Connect AI" and opens the panel. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { configProvider, getProviderStatus, hasStoredToken, logout, signIn,
  getModelCatalog, registerModel, listModels, deleteModel, bindModel } = vi.hoisted(() => ({
  configProvider: vi.fn(),
  getProviderStatus: vi.fn(),
  hasStoredToken: vi.fn(),
  logout: vi.fn(),
  signIn: vi.fn(),
  // MODEL-REGISTRY-1c: ProviderSettings now composes <ModelRegistry/>, which calls these on mount.
  // Stub them so mounting the panel never reaches a real fetch (the model-pool surface itself is
  // covered by ModelRegistry.test.jsx).
  getModelCatalog: vi.fn(),
  registerModel: vi.fn(),
  listModels: vi.fn(),
  deleteModel: vi.fn(),
  bindModel: vi.fn(),
}));

vi.mock("./bff.js", () => ({
  configProvider, getProviderStatus, hasStoredToken, logout, signIn,
  getModelCatalog, registerModel, listModels, deleteModel, bindModel,
}));

import ProviderSettings from "./genui/ProviderSettings.jsx";
import { LeftRail } from "./panes.jsx";

const rail = { width: 270, agents: ["ws0_default"], activeAgent: "ws0_default" };

beforeEach(() => {
  configProvider.mockReset().mockResolvedValue({ ok: true, plane: "grading", provider: "openai", last_tested: "2026-06-24T00:00:00+00:00" });
  getProviderStatus.mockReset().mockResolvedValue({ planes: {} });
  hasStoredToken.mockReset().mockReturnValue(false);
  logout.mockReset();
  signIn.mockReset();
  getModelCatalog.mockReset().mockResolvedValue({ providers: { openai: [], anthropic: [], azure: { models: [], note: "" } } });
  registerModel.mockReset().mockResolvedValue({});
  listModels.mockReset().mockResolvedValue({ models: [] });
  deleteModel.mockReset().mockResolvedValue({});
  bindModel.mockReset().mockResolvedValue({});
});

describe("ProviderSettings — CE-PROVIDER-UI Build B", () => {
  it("A: renders both capability slots — grading required, assistant optional", async () => {
    render(<ProviderSettings />);
    // grading engine, marked required (exact-match the heading — "grading engine" also appears in
    // the degradation copy, so a loose /Grading engine/i would collide with our own description).
    expect(await screen.findByText("Grading engine")).toBeInTheDocument();
    expect(screen.getByText(/required/i)).toBeInTheDocument();
    // authoring assistant, marked optional
    expect(screen.getByText("Authoring assistant")).toBeInTheDocument();
    expect(screen.getByText(/optional/i)).toBeInTheDocument();
    // graceful-degradation copy
    expect(screen.getByText(/grade now/i)).toBeInTheDocument();
  });

  it("B: entering a key + Test & save calls configProvider with the entered value, via a masked input", async () => {
    render(<ProviderSettings />);
    const keyInput = await screen.findByTestId("grading-api-key");
    // the secret never echoes — it's a password input
    expect(keyInput).toHaveAttribute("type", "password");
    fireEvent.change(keyInput, { target: { value: "sk-test-123" } });
    fireEvent.click(screen.getByTestId("grading-test-save"));
    await waitFor(() =>
      expect(configProvider).toHaveBeenCalledWith(
        expect.objectContaining({ plane: "grading", provider: "openai", api_key: "sk-test-123" }),
      ),
    );
  });

  it("C: a configured grading plane renders the connected badge (getProviderStatus mocked)", async () => {
    getProviderStatus.mockResolvedValue({
      planes: { grading: { configured: true, provider: "openai", model: "gpt-4o", last_tested: "2026-06-24T00:00:00+00:00" } },
    });
    render(<ProviderSettings />);
    expect(await screen.findByTestId("grading-status-badge")).toHaveTextContent(/connected/i);
  });

  it("C2: an unconfigured plane shows needs-setup, not connected", async () => {
    getProviderStatus.mockResolvedValue({ planes: {} });
    render(<ProviderSettings />);
    expect(await screen.findByTestId("grading-status-badge")).toHaveTextContent(/needs setup/i);
  });

  it("B2: the assistant slot writes plane:assistant with provider anthropic", async () => {
    render(<ProviderSettings />);
    const keyInput = await screen.findByTestId("assistant-api-key");
    fireEvent.change(keyInput, { target: { value: "sk-ant-xyz" } });
    fireEvent.click(screen.getByTestId("assistant-test-save"));
    await waitFor(() =>
      expect(configProvider).toHaveBeenCalledWith(
        expect.objectContaining({ plane: "assistant", provider: "anthropic", api_key: "sk-ant-xyz" }),
      ),
    );
  });

  it("E: Advanced mode reveals per-role Azure rows (provider/endpoint/deployment)", async () => {
    render(<ProviderSettings />);
    fireEvent.click(await screen.findByTestId("grading-advanced-toggle"));
    expect(await screen.findByTestId("grading-role-risk_judge")).toBeInTheDocument();
    expect(screen.getByTestId("grading-role-policy_judge")).toBeInTheDocument();
    expect(screen.getByTestId("grading-role-faithfulness_judge")).toBeInTheDocument();
  });
});

describe("LeftRail — CE-PROVIDER-UI Build B (D): the 'Connect AI' session-menu entry", () => {
  it("D: the session-menu shows 'Connect AI' and clicking it opens the ProviderSettings panel", async () => {
    render(<LeftRail {...rail} />);
    fireEvent.click(screen.getByLabelText("Session menu"));
    const item = screen.getByRole("menuitem", { name: /Connect AI/i });
    expect(item).toBeInTheDocument();
    fireEvent.click(item);
    // the panel mounts — its grading slot heading appears (exact-match: "Grading engine" recurs in
    // the panel's own degradation copy, so a regex would match more than the heading)
    expect(await screen.findByText("Grading engine")).toBeInTheDocument();
  });

  it("D2: the Connect-AI panel has a close affordance that dismisses it", async () => {
    render(<LeftRail {...rail} />);
    fireEvent.click(screen.getByLabelText("Session menu"));
    fireEvent.click(screen.getByRole("menuitem", { name: /Connect AI/i }));
    expect(await screen.findByText("Grading engine")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("provider-settings-close"));
    await waitFor(() => expect(screen.queryByText("Grading engine")).toBeNull());
  });
});
