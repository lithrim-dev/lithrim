/* palette.test.jsx — CMDK-1: the ⌘K command palette is REAL (UI-pass 2026-07-04 P1 #6).

   The shell shipped two search affordances ("Search or run a command… ⌘K" in the top bar,
   "Search ⌘K" in the rail) that were inert static divs — dead chrome advertising a shortcut
   that did nothing. The palette makes them honest: fuzzy-filter over the core ACTIONS, the
   workspace's EVALUATIONS, and the browsable CASES (the CASE-BROWSER-1 read), keyboard-first
   (↑/↓/Enter/Esc). A-SAFE: the paid "Run live" entry is a CALLBACK the App routes through the
   S-BS-80 cost-confirm (requestRun(true)) — the palette itself never spends. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("./bff.js", () => ({ listCaseBrowser: vi.fn() }));

import { CommandPalette } from "./palette.jsx";
import { listCaseBrowser } from "./bff.js";

const CASES = {
  cases: [
    { case_id: "cv_mts_005_dissent", labeled: true, defect: "DISSENT_ERASURE", runs: 0, baseline: "none" },
    { case_id: "cv_mts_001_clean", labeled: true, defect: null, runs: 4, baseline: "stale" },
  ],
};

beforeEach(() => {
  listCaseBrowser.mockReset();
  listCaseBrowser.mockResolvedValue(CASES);
});

const noop = () => {};
const baseProps = { open: true, onClose: noop, agent: "ws0_default", agents: [], onSwitchAgent: noop, onSelectCase: noop };

describe("CommandPalette — CMDK-1", () => {
  it("renders actions + evaluations + browsable cases, with the case label as the hint", async () => {
    const run = vi.fn();
    render(
      <CommandPalette {...baseProps} agents={["ws0_default", "repro_agent"]} activeAgent="ws0_default"
        actions={[{ id: "run-eval", label: "Run eval — replay the selected case for $0", run }]} />,
    );
    expect(screen.getByText(/Run eval — replay/)).toBeInTheDocument();
    expect(screen.getByText("repro_agent")).toBeInTheDocument(); // the OTHER evaluation (never the active one)
    expect(screen.queryByTestId("cmdk-item-ws0_default")).toBeNull();
    expect(await screen.findByText("cv_mts_005_dissent")).toBeInTheDocument();
    expect(screen.getByText("Dissent erasure")).toBeInTheDocument(); // defect hint via flagLabel
    expect(screen.getByText("clean")).toBeInTheDocument();
  });

  it("typing filters; Enter runs the selected item and closes", async () => {
    const run = vi.fn();
    const onClose = vi.fn();
    render(
      <CommandPalette {...baseProps} onClose={onClose}
        actions={[
          { id: "run-eval", label: "Run eval — $0 replay", run },
          { id: "report", label: "Open report", run: vi.fn() },
        ]} />,
    );
    const input = screen.getByTestId("cmdk-input");
    fireEvent.change(input, { target: { value: "replay" } });
    expect(screen.queryByText("Open report")).toBeNull(); // filtered out
    fireEvent.keyDown(input, { key: "Enter" });
    expect(run).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalled();
  });

  it("clicking a case row calls onSelectCase with the id (arming the Run buttons)", async () => {
    const onSelectCase = vi.fn();
    render(<CommandPalette {...baseProps} onSelectCase={onSelectCase} actions={[]} />);
    fireEvent.click(await screen.findByText("cv_mts_001_clean"));
    expect(onSelectCase).toHaveBeenCalledWith("cv_mts_001_clean");
  });

  it("↓ moves the selection before Enter (keyboard-first)", async () => {
    const first = vi.fn();
    const second = vi.fn();
    render(
      <CommandPalette {...baseProps}
        actions={[{ id: "a", label: "First action", run: first }, { id: "b", label: "Second action", run: second }]} />,
    );
    const input = screen.getByTestId("cmdk-input");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(second).toHaveBeenCalledTimes(1);
    expect(first).not.toHaveBeenCalled();
  });

  it("Escape closes without running anything; closed renders nothing", () => {
    const onClose = vi.fn();
    const run = vi.fn();
    const { rerender } = render(
      <CommandPalette {...baseProps} onClose={onClose} actions={[{ id: "a", label: "First action", run }]} />,
    );
    fireEvent.keyDown(screen.getByTestId("cmdk-input"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
    expect(run).not.toHaveBeenCalled();
    rerender(<CommandPalette {...baseProps} open={false} actions={[]} />);
    expect(screen.queryByTestId("cmdk")).toBeNull();
  });

  it("offline case fetch degrades to actions-only (never a crash)", async () => {
    listCaseBrowser.mockRejectedValue(new Error("offline"));
    render(<CommandPalette {...baseProps} actions={[{ id: "a", label: "First action", run: noop }]} />);
    expect(screen.getByText("First action")).toBeInTheDocument();
  });
});
