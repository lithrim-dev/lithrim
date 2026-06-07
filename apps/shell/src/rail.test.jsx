/* rail.test.jsx — CRUD-1 (D4): the LeftRail lists the REAL config-plane agents and is the
   switch/delete surface. The seed default + the last agent hide their delete affordance
   (the BFF 422 guards, reflected in the UI). */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LeftRail } from "./panes.jsx";

const base = { width: 270, onNewEval: () => {}, onSwitchAgent: () => {}, onDeleteAgent: () => {} };

describe("CRUD-1 LeftRail agents switcher", () => {
  it("renders the real agents and switches on click", () => {
    const onSwitchAgent = vi.fn();
    render(<LeftRail {...base} agents={["ws0_default", "eval-1"]} activeAgent="ws0_default" onSwitchAgent={onSwitchAgent} />);
    expect(screen.getByText("ws0_default")).toBeInTheDocument();
    expect(screen.getByText("eval-1")).toBeInTheDocument();
    fireEvent.click(screen.getByText("eval-1"));
    expect(onSwitchAgent).toHaveBeenCalledWith("eval-1");
  });

  it("hides delete for the seed default, shows + fires it for a deletable agent", () => {
    const onDeleteAgent = vi.fn();
    render(<LeftRail {...base} agents={["ws0_default", "eval-1"]} activeAgent="eval-1" onDeleteAgent={onDeleteAgent} />);
    expect(screen.queryByLabelText("Delete ws0_default")).toBeNull(); // seed default guarded
    fireEvent.click(screen.getByLabelText("Delete eval-1"));
    expect(onDeleteAgent).toHaveBeenCalledWith("eval-1");
  });

  it("hides delete when only one agent remains (last-agent guard reflected)", () => {
    render(<LeftRail {...base} agents={["eval-1"]} activeAgent="eval-1" />);
    expect(screen.queryByLabelText("Delete eval-1")).toBeNull();
  });

  it("shows an empty-state when there are no agents", () => {
    render(<LeftRail {...base} agents={[]} activeAgent={null} />);
    expect(screen.getByText(/No evaluations yet/i)).toBeInTheDocument();
  });

  it("the + button triggers New evaluation", () => {
    const onNewEval = vi.fn();
    render(<LeftRail {...base} agents={["ws0_default"]} activeAgent="ws0_default" onNewEval={onNewEval} />);
    fireEvent.click(screen.getByLabelText("New evaluation"));
    expect(onNewEval).toHaveBeenCalled();
  });
});
