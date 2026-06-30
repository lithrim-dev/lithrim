/* ToolBuilder — TOOL-AUTHOR-1: declare a kind:tool connector from the UI. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ToolBuilder from "./ToolBuilder.jsx";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("ToolBuilder", () => {
  it("renders the connector fields, seeded", () => {
    render(<ToolBuilder agent="ws_a" seed={{ id: "my_hermes", implements: "tool.terminology", command: "hermes", args: "--db /x mcp" }} />);
    expect(screen.getByText(/Connect a tool/i)).toBeInTheDocument();
    expect(screen.getByLabelText("tool id")).toHaveValue("my_hermes");
    expect(screen.getByLabelText("command")).toHaveValue("hermes");
  });

  it("Test connection posts the manifest and shows the reachable tools", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, tools: ["search", "subsumed_by"] }) });
    vi.stubGlobal("fetch", fetchMock);
    render(<ToolBuilder agent="ws_a" seed={{ id: "my_hermes", implements: "tool.terminology", command: "hermes", args: "--db /x mcp" }} />);
    fireEvent.click(screen.getByText(/Test connection/i));
    await waitFor(() => expect(screen.getByTestId("tool-test-result")).toHaveTextContent(/reachable/i));
    // it hit the health-check route with a manifest carrying the stdio command
    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/v1\/tools\/test$/);
    expect(JSON.parse(opts.body).manifest.service.mcp.command).toBe("hermes");
  });

  it("Create tool posts the manifest to /v1/tools and fires onResult", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok", tool_id: "my_hermes" }) });
    vi.stubGlobal("fetch", fetchMock);
    const onResult = vi.fn();
    render(<ToolBuilder agent="ws_a" seed={{ id: "my_hermes", implements: "tool.terminology", command: "hermes", args: "--db /x mcp" }} onResult={onResult} />);
    fireEvent.click(screen.getByTestId("tool-save"));
    await waitFor(() => expect(onResult).toHaveBeenCalled());
    const [url, opts] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/v1\/tools$/);
    const body = JSON.parse(opts.body);
    expect(body.manifest.id).toBe("my_hermes");
    expect(body.manifest.kind).toBe("tool");
    expect(body.manifest.service.mcp.args).toEqual(["--db", "/x", "mcp"]);
  });
});
