/* WorkspaceSwitcher — the chrome pill that switches the active domain setup. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { WorkspaceSwitcher } from "./app.jsx";

const WS = [
  { name: "default", pack: "_core" },
  { name: "clinical", pack: "healthcare" },
];

describe("WorkspaceSwitcher", () => {
  it("shows the active workspace and opens to list all (with their pinned pack)", () => {
    render(<WorkspaceSwitcher active="default" workspaces={WS} onSwitch={() => {}} onCreate={() => {}} />);
    expect(screen.getByTitle("Switch workspace")).toHaveTextContent("default");
    fireEvent.click(screen.getByTitle("Switch workspace"));
    expect(screen.getByText("clinical")).toBeInTheDocument();
    expect(screen.getByText("healthcare")).toBeInTheDocument(); // the pinned domain pack
  });

  it("switches to another workspace", () => {
    const onSwitch = vi.fn();
    render(<WorkspaceSwitcher active="default" workspaces={WS} onSwitch={onSwitch} onCreate={() => {}} />);
    fireEvent.click(screen.getByTitle("Switch workspace"));
    fireEvent.click(screen.getByText("clinical"));
    expect(onSwitch).toHaveBeenCalledWith("clinical");
  });

  it("does NOT re-switch when clicking the already-active workspace", () => {
    const onSwitch = vi.fn();
    render(<WorkspaceSwitcher active="default" workspaces={WS} onSwitch={onSwitch} onCreate={() => {}} />);
    fireEvent.click(screen.getByTitle("Switch workspace"));
    // "default" is in the pill AND the active menu item — click the menu item (the last match)
    const matches = screen.getAllByText("default");
    fireEvent.click(matches[matches.length - 1]);
    expect(onSwitch).not.toHaveBeenCalled();
  });

  it("creates a new workspace via the inline form (Enter submits)", () => {
    const onCreate = vi.fn().mockResolvedValue();
    render(<WorkspaceSwitcher active="default" workspaces={WS} onSwitch={() => {}} onCreate={onCreate} />);
    fireEvent.click(screen.getByTitle("Switch workspace"));
    fireEvent.click(screen.getByText("New workspace"));
    const input = screen.getByPlaceholderText("workspace name");
    fireEvent.change(input, { target: { value: "team-x" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onCreate).toHaveBeenCalledWith("team-x", "_core"); // name + the picked domain pack
  });

  // F1: a name with spaces is rejected CLIENT-SIDE (matching the server rule) — surfaced inline,
  // onCreate never fired (no silent failure).
  it("blocks an invalid name (spaces) with an inline error and does NOT call onCreate", () => {
    const onCreate = vi.fn().mockResolvedValue();
    render(<WorkspaceSwitcher active="default" workspaces={WS} onSwitch={() => {}} onCreate={onCreate} />);
    fireEvent.click(screen.getByTitle("Switch workspace"));
    fireEvent.click(screen.getByText("New workspace"));
    const input = screen.getByPlaceholderText("workspace name");
    fireEvent.change(input, { target: { value: "Team Onboarding" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onCreate).not.toHaveBeenCalled();
    expect(screen.getByTestId("ws-create-error")).toBeInTheDocument();
    // editing the name clears the error
    fireEvent.change(input, { target: { value: "Team_Onboarding" } });
    expect(screen.queryByTestId("ws-create-error")).not.toBeInTheDocument();
  });

  // F1: a server reject (onCreate throws, e.g. a 400) is surfaced inline, not swallowed to the console.
  it("surfaces a server reject from onCreate inline", async () => {
    const onCreate = vi.fn().mockRejectedValue(new Error("invalid workspace name 'x' (use alphanumerics, '-' or '_')"));
    render(<WorkspaceSwitcher active="default" workspaces={WS} onSwitch={() => {}} onCreate={onCreate} />);
    fireEvent.click(screen.getByTitle("Switch workspace"));
    fireEvent.click(screen.getByText("New workspace"));
    const input = screen.getByPlaceholderText("workspace name");
    fireEvent.change(input, { target: { value: "team-y" } }); // passes client validation → reaches onCreate
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onCreate).toHaveBeenCalledWith("team-y", "_core");
    expect(await screen.findByTestId("ws-create-error")).toHaveTextContent(/invalid workspace name/);
  });
});
