/* VerdictCard.test.jsx — the verdict card must (a) render REAL output (no hardcoded
   DEMO masquerading as a verdict) and (b) drive its color/icon from the verdict, so a
   REJECT reads negative (coral/fail), not a green "pass" pill + coral check.
   [[no-static-components-in-live-eval-ui]] */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import VerdictCard from "./VerdictCard.jsx";

describe("VerdictCard — verdict-driven, real-data only", () => {
  it("a REJECT renders the fail (coral) badge, NOT the pass (green) one", () => {
    const { container, getByText } = render(
      <VerdictCard verdict="REJECT" confidence="0.9" agreement="1 / 3" question="Q?" answer="A." pillar="Faithfulness" pillarStatus="flagged" />,
    );
    getByText("REJECT");
    const badge = container.querySelector(".tag");
    expect(badge.className).toMatch(/\bfail\b/); // coral/fail tone
    expect(badge.className).not.toMatch(/\bpass\b/); // never the green pass pill
  });

  it("an APPROVE/PASS renders the pass (green) badge", () => {
    const { container } = render(<VerdictCard verdict="approve" confidence="1.0" agreement="3 / 3" question="Q?" answer="A." />);
    const badge = container.querySelector(".tag");
    expect(badge.className).toMatch(/\bpass\b/);
    expect(badge.className).not.toMatch(/\bfail\b/);
  });

  it("output-less mount renders an honest empty state — NOT a fabricated DEMO verdict", () => {
    const { container, queryByText, getByText } = render(<VerdictCard />);
    getByText(/no verdict yet/i); // honest placeholder
    expect(queryByText("Sample verdict")).toBeNull(); // no fake title
    expect(container.textContent).not.toMatch(/0\.96|3 \/ 3|refund policy/); // no DEMO leak
    expect(container.querySelector(".tag")).toBeNull(); // no fake verdict badge
  });

  it("judge-agreement dots reflect the real count (1 / 3 -> 1 filled, 2 empty)", () => {
    const { container } = render(<VerdictCard verdict="reject" agreement="1 / 3" question="Q?" answer="A." />);
    const dots = container.querySelectorAll(".agree-dots .ad");
    expect(dots.length).toBe(3);
    expect(container.querySelectorAll(".agree-dots .ad.no").length).toBe(2); // 2 of 3 not-agreeing
  });
});
