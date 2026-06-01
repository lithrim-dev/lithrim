/* app.test.jsx — Shell chrome smoke. Guards the gap the WS-5c critique found: no
   test rendered the Shell TopBar, so a stray `}` literal at app.jsx:23 (post-close
   commit 0c13d3f) passed build + 18 tests undetected. This renders the Shell and
   asserts the titlebar is clean: the mode-switch is present and no stray brace leaks. */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./app.jsx";

describe("Shell chrome (App titlebar)", () => {
  it("renders the titlebar with the mode-switch and no stray brace literal", () => {
    const { container } = render(<App mode="shell" setMode={() => {}} />);

    // the Shell↔Journey segmented control is in the chrome
    expect(screen.getByRole("tab", { name: "Shell" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Journey" })).toBeInTheDocument();

    const titlebar = container.querySelector(".titlebar");
    expect(titlebar).toBeTruthy();
    // the clinical/Scribe crumb renders in the titlebar...
    expect(titlebar.textContent).toContain("Scribe Agent v4");
    // ...and no stray `}` text node leaked into it (the 0c13d3f regression)
    expect(titlebar.textContent).not.toContain("}");
  });
});
