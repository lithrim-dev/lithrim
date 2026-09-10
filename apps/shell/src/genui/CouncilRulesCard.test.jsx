/* CouncilRulesCard.test.jsx — UI-JOURNEY-1 (B10): the council's rules, readable. */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import CouncilRulesCard from "./CouncilRulesCard.jsx";

const RULES = {
  pack: "_core", panel: ["risk_judge", "policy_judge", "faithfulness_judge"], reviewer_roster: ["ragtruth_detector"], min_valid_judges: 2,
  rules: [
    { name: "tier rules", text: "Tier 1: one judge with evidence blocks." },
    { name: "the hesitant or contradicted judge (withstands)", text: "A finding the signals contradict is removed." },
  ],
};

describe("CouncilRulesCard", () => {
  it("names the panel, the agent's roster and each rule", () => {
    render(<CouncilRulesCard {...RULES} />);
    expect(screen.getByTestId("council-roster").textContent).toMatch(/risk_judge.*this agent runs: ragtruth_detector/);
    expect(screen.getByTestId("council-rule-the-hesitant-or-contradicted-judge-withstands-").textContent).toMatch(/signals contradict/);
    expect(screen.getByTestId("council-rules").textContent).toMatch(/needs 2 answers/);
  });
  it("an empty output is an honest empty state", () => {
    render(<CouncilRulesCard />);
    expect(screen.getByTestId("council-rules-empty")).toBeInTheDocument();
  });
});
