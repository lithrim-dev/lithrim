/* app.test.jsx — Shell chrome smoke. Guards the gap the WS-5c critique found: no
   test rendered the Shell TopBar, so a stray `}` literal at app.jsx:23 (post-close
   commit 0c13d3f) passed build + 18 tests undetected. This renders the Shell and
   asserts the titlebar is clean: the mode-switch is present and no stray brace leaks. */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./app.jsx";

describe("Shell chrome (App titlebar)", () => {
  it("renders the titlebar with the Evaluations crumb and no stray brace literal", () => {
    const { container } = render(<App mode="shell" setMode={() => {}} />);

    const titlebar = container.querySelector(".titlebar");
    expect(titlebar).toBeTruthy();
    // the workspace pill + the Evaluations crumb render in the titlebar...
    expect(titlebar.textContent).toContain("Evaluations");
    // ...and no stray `}` text node leaked into it (the 0c13d3f regression this test guards)
    expect(titlebar.textContent).not.toContain("}");
  });

  // CONV-FIRST (SPEC_CONVERSATIONAL_FIRST): the conversation is the product. The auxiliary
  // artifact pane is CLOSED by default — the center conversation fills the screen, and the
  // pane opens only on an explicit drill-down. NON-VACUOUS: with the old `open=true` default
  // the `.artifact` section renders and this fails.
  it("CONV-FIRST: the artifact pane is CLOSED by default (conversation fills the center)", () => {
    const { container } = render(<App mode="shell" setMode={() => {}} />);
    expect(container.querySelector(".artifact")).toBeNull();
  });
});
