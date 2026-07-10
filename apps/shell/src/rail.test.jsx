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
    expect(screen.getByText("Sample evaluation")).toBeInTheDocument(); // friendly label for ws0_default
    expect(screen.getByText("Evaluation 1")).toBeInTheDocument(); // friendly label for eval-1
    fireEvent.click(screen.getByText("Evaluation 1"));
    expect(onSwitchAgent).toHaveBeenCalledWith("eval-1"); // the raw id still drives the switch
  });

  it("hides delete for the seed default, two-step confirms a deletable agent", () => {
    const onDeleteAgent = vi.fn();
    render(<LeftRail {...base} agents={["ws0_default", "eval-1"]} activeAgent="eval-1" onDeleteAgent={onDeleteAgent} />);
    expect(screen.queryByLabelText("Delete ws0_default")).toBeNull(); // seed default guarded
    // DELETE-CONFIRM-1: a single click ARMS the confirm — it must NOT delete (the audit row dies with it).
    fireEvent.click(screen.getByLabelText("Delete eval-1"));
    expect(onDeleteAgent).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("Confirm delete eval-1"));
    expect(onDeleteAgent).toHaveBeenCalledWith("eval-1");
  });

  it("DELETE-CONFIRM-1: cancel disarms the confirm and never deletes", () => {
    const onDeleteAgent = vi.fn();
    render(<LeftRail {...base} agents={["ws0_default", "eval-1"]} activeAgent="eval-1" onDeleteAgent={onDeleteAgent} />);
    fireEvent.click(screen.getByLabelText("Delete eval-1")); // arm
    expect(screen.getByLabelText("Confirm delete eval-1")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Cancel delete eval-1")); // disarm
    expect(screen.queryByLabelText("Confirm delete eval-1")).toBeNull(); // back to the delete button
    expect(screen.getByLabelText("Delete eval-1")).toBeInTheDocument();
    expect(onDeleteAgent).not.toHaveBeenCalled();
  });

  it("DELETE-CONFIRM-1: arming a delete does not switch the active agent (stopPropagation)", () => {
    const onSwitchAgent = vi.fn();
    render(<LeftRail {...base} agents={["ws0_default", "eval-1"]} activeAgent="ws0_default" onSwitchAgent={onSwitchAgent} />);
    fireEvent.click(screen.getByLabelText("Delete eval-1")); // arming must not bubble to the row switch
    expect(onSwitchAgent).not.toHaveBeenCalled();
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
