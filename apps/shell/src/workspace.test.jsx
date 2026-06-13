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
    expect(onCreate).toHaveBeenCalledWith("team-x");
  });
});
