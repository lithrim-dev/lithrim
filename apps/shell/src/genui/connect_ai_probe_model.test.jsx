/* connect_ai_probe_model.test.jsx — CONNECT-AI-COMPAT-1: the openai_compatible probe-model field.

   The BFF probe falls back to "gpt-4o" when no model rides the connect (_probe_provider
   default_model) and ProvidersSection deliberately sent NO model — so an OpenAI-compatible
   endpoint that doesn't serve a model named gpt-4o (Azure Foundry serverless Mistral/Llama,
   vLLM, …) could NEVER connect. The fix: an OPTIONAL "probe model" input, openai_compatible
   ONLY (a role-less azure `model` is NOT write-inert — it writes the global deployment vars),
   threaded through configProvider's existing `model` param.

   A: openai_compatible → the probe-model input appears; openai + azure never show it.
   B: save WITHOUT a probe model → configProvider carries NO model key (the fallback stands).
   C: save WITH a typed probe model → configProvider carries it; the key clears on success. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { configProvider } = vi.hoisted(() => ({ configProvider: vi.fn() }));
vi.mock("../bff.js", () => ({ configProvider }));

import ProvidersSection from "./ProvidersSection.jsx";

beforeEach(() => {
  configProvider.mockReset().mockResolvedValue({
    ok: true, plane: "grading", provider: "openai_compatible", last_tested: "2026-07-07T00:00:00+00:00",
  });
});

const pickCompat = () => {
  fireEvent.change(screen.getByTestId("providers-provider"), { target: { value: "openai_compatible" } });
  fireEvent.change(screen.getByTestId("providers-endpoint"), { target: { value: "https://my-foundry.example/v1" } });
  fireEvent.change(screen.getByTestId("providers-key"), { target: { value: "sk-compat-secret" } });
};

describe("CONNECT-AI-COMPAT-1 — the openai_compatible probe-model field", () => {
  it("A: the input shows for openai_compatible ONLY (openai + azure hide it)", () => {
    render(<ProvidersSection connected={[]} />);
    expect(screen.queryByTestId("providers-probe-model")).toBeNull(); // openai (the default)
    fireEvent.change(screen.getByTestId("providers-provider"), { target: { value: "openai_compatible" } });
    expect(screen.getByTestId("providers-probe-model")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("providers-provider"), { target: { value: "azure" } });
    expect(screen.queryByTestId("providers-probe-model")).toBeNull(); // azure: model is NOT write-inert
  });

  it("B: saving without a probe model sends NO model (the gpt-4o fallback stands)", async () => {
    render(<ProvidersSection connected={[]} />);
    pickCompat();
    fireEvent.click(screen.getByTestId("providers-save"));
    await waitFor(() => expect(configProvider).toHaveBeenCalled());
    expect(configProvider.mock.calls[0][0].model).toBeUndefined();
  });

  it("C: a typed probe model rides configProvider's model param; the key clears on success", async () => {
    const { container } = render(<ProvidersSection connected={[]} />);
    pickCompat();
    fireEvent.change(screen.getByTestId("providers-probe-model"), { target: { value: "mistral-large-2411" } });
    fireEvent.click(screen.getByTestId("providers-save"));
    await waitFor(() =>
      expect(configProvider).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "openai_compatible",
          endpoint: "https://my-foundry.example/v1",
          model: "mistral-large-2411",
        }),
      ),
    );
    await waitFor(() => expect(screen.getByTestId("providers-key").value).toBe(""));
    expect(container.innerHTML).not.toContain("sk-compat-secret");
  });
});
