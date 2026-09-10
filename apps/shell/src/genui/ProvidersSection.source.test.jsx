/* ProvidersSection.source.test.jsx — UI-JOURNEY-1 (B10, audit quirk 5): which key is in force. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  connectProvider: vi.fn(),
  testProvider: vi.fn(),
  saveProviderConfig: vi.fn(),
  probeProvider: vi.fn(),
}));

import ProvidersSection from "./ProvidersSection.jsx";

describe("ProvidersSection — the key's source", () => {
  it("says an in-app key overrides the environment, and an environment key will be overridden", () => {
    render(<ProvidersSection connected={["azure"]} sources={{ azure: "in-app", openai: "environment", anthropic: "unset" }} />);
    const select = screen.getByTestId("providers-provider");
    fireEvent.change(select, { target: { value: "azure" } });
    expect(screen.getByTestId("providers-source").dataset.source).toBe("in-app");
    expect(screen.getByTestId("providers-source").textContent).toMatch(/overrides a key set in the environment/);
    fireEvent.change(select, { target: { value: "openai" } });
    expect(screen.getByTestId("providers-source").textContent).toMatch(/from the environment.*will override it/);
  });
  it("renders no source line without the readout (an older service)", () => {
    render(<ProvidersSection connected={[]} />);
    expect(screen.queryByTestId("providers-source")).toBeNull();
  });
});
