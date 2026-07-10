/* CostModal.test.jsx — A11Y (Theme A / A2): the paid-run gate is labelled by its title, Escape
   cancels (a discoverable keyboard exit, not only a backdrop click), and confirm is focused on
   open. The spend-safety behavior (Escape never fires onConfirm) is the load-bearing guarantee. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CostModal } from "./CostModal.jsx";

const base = { open: true, title: "Run a paid evaluation?", body: "About $0.15.", onConfirm: () => {}, onCancel: () => {} };

describe("CostModal a11y", () => {
  it("is labelled by its title (aria-labelledby → the title node)", () => {
    render(<CostModal {...base} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-labelledby", "cost-modal-title");
    expect(document.getElementById("cost-modal-title")).toHaveTextContent("Run a paid evaluation?");
  });

  it("Escape cancels (and never confirms the spend)", () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(<CostModal {...base} onCancel={onCancel} onConfirm={onConfirm} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("does NOT cancel on Escape while a run is busy (no mid-spend dismiss)", () => {
    const onCancel = vi.fn();
    render(<CostModal {...base} busy onCancel={onCancel} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("focuses the confirm button on open (keyboard lands inside the dialog)", () => {
    render(<CostModal {...base} />);
    expect(screen.getByTestId("cost-confirm")).toHaveFocus();
  });
});
