/* CalibrationChart.test.jsx — real-data only, no demo curve / no hardcoded
   "well-calibrated 2.4%". Output-less -> honest empty state; the badge is driven by
   the real ECE, not a fixed green claim. [[no-static-components-in-live-eval-ui]] */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import CalibrationChart from "./CalibrationChart.jsx";

describe("CalibrationChart — real-data only", () => {
  it("output-less mount renders an honest empty state — NOT the demo curve/metrics", () => {
    const { container, getByText, queryByText } = render(<CalibrationChart />);
    getByText(/no calibration yet/i);
    expect(queryByText("2.4%")).toBeNull(); // no DEMO ece
    expect(queryByText(/well-calibrated/i)).toBeNull(); // no fixed claim
    expect(container.querySelectorAll("svg rect").length).toBe(0); // no demo bars
  });

  it("renders the real curve + metrics from output (points/ece/brier)", () => {
    const points = [{ p: 0.2, o: 0.18 }, { p: 0.8, o: 0.83 }];
    const { container, getByText } = render(<CalibrationChart points={points} ece="3.1%" brier="0.061" />);
    getByText("3.1%");
    getByText("0.061");
    expect(container.querySelectorAll("svg rect").length).toBe(points.length); // one bar per real bin
  });

  it("a high ECE is NOT badged 'well-calibrated'", () => {
    const { container, queryByText } = render(<CalibrationChart points={[{ p: 0.5, o: 0.1 }]} ece="9.9%" brier="0.5" />);
    expect(queryByText(/well-calibrated/i)).toBeNull(); // 9.9% is not well-calibrated
    expect(container.querySelector(".tag")?.className || "").not.toMatch(/\bpass\b/);
  });
});
