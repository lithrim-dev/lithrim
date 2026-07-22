/* copy.test.jsx — UX-COPY-1: the label helpers + VerdictCard renders plain language, not raw
   engine codes (no "BLOCK", no "faithfulness_judge", no "MEDICATION_NOT_IN_TRANSCRIPT"). */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { verdictLabel, roleLabel, roleLabelsFor, reviewerLabel, flagLabel, friendlyError, voteReason } from "./copy.js";
import VerdictCard from "./VerdictCard.jsx";

describe("UX-COPY-1 — label helpers", () => {
  it("verdictLabel maps codes to plain outcomes", () => {
    expect(verdictLabel("BLOCK")).toBe("Flagged");
    expect(verdictLabel("reject")).toBe("Flagged");
    expect(verdictLabel("FAIL")).toBe("Flagged");
    expect(verdictLabel("WARN")).toBe("Needs a look");
    expect(verdictLabel("needs_review")).toBe("Needs a look");
    expect(verdictLabel("PASS")).toBe("Passed");
    expect(verdictLabel("approve")).toBe("Passed");
  });
  it("roleLabel turns a judge id into a reviewer name", () => {
    expect(roleLabel("faithfulness_judge")).toBe("Faithfulness reviewer");
    expect(roleLabel("risk_judge")).toBe("Risk reviewer");
    expect(roleLabel("chat_assistant")).toBe("Assistant");
  });
  it("flagLabel makes a CODE readable", () => {
    expect(flagLabel("MEDICATION_NOT_IN_TRANSCRIPT")).toBe("Medication not in transcript");
    expect(flagLabel("HISTORY_OMISSION")).toBe("History omission");
  });
  it("voteReason reads reason || explanation (one helper for LLM + reward-model judges)", () => {
    expect(voteReason({ reason: "llm why" })).toBe("llm why");
    expect(voteReason({ explanation: "rm why" })).toBe("rm why");
    expect(voteReason({ reason: "", explanation: "rm why" })).toBe("rm why");
    expect(voteReason({})).toBe("");
    expect(voteReason(null)).toBe("");
  });

  it("roleLabelsFor disambiguates colliding labels with the role id (DUP-ROLE-LABEL-1)", () => {
    const m = roleLabelsFor(["generalist_judge", "generalist_reviewer", "risk_judge"]);
    expect(m.generalist_judge).toBe("Generalist reviewer (generalist_judge)");
    expect(m.generalist_reviewer).toBe("Generalist reviewer (generalist_reviewer)");
    expect(m.risk_judge).toBe("Risk reviewer");
  });

  it("friendlyError never leaks HTTP/paths/JSON; maps known causes; keeps validation reasons", () => {
    // the screenshot case: POST + 404 + JSON detail + a filesystem path → a clean sentence
    const screenshot =
      'POST /v1/run-eval → 404: {"detail":"\\"agent \'ws0_default\' not found in config DB out/workspaces/clinical_scribe/config.sqlite\\""}';
    const out = friendlyError(screenshot);
    expect(out).toBe("This evaluation isn't set up yet — create or pick one, then try again.");
    expect(out).not.toMatch(/POST|\/v1\/|404|\.sqlite|\/Users\/|detail/i); // no machinery leaks
    // known causes
    expect(friendlyError("Failed to fetch")).toMatch(/couldn't reach the server/i);
    expect(friendlyError("Error: 500 Internal Server Error")).toMatch(/server/i);
    expect(friendlyError("")).toMatch(/something went wrong/i);
    // a real validation reason is CLEANED but KEPT (no generic swallow)
    expect(friendlyError("POST /v1/judges → 422: role collision: escalation_judge already exists"))
      .toMatch(/role collision/i);
    // a raw stack/path-only dump → generic, never the path
    const dump = "Traceback (most recent call last): File /app/x.py line 9";
    expect(friendlyError(dump)).toMatch(/something went wrong/i);
    expect(friendlyError(dump)).not.toMatch(/\.py|\/app\//);
  });
});

describe("UX-COPY-1 — VerdictCard renders plain language", () => {
  const props = {
    verdict: "BLOCK",
    votes: [
      { role: "faithfulness_judge", vote: "BLOCK", confidence: 0.43, reason: "drops a stated value" },
      { role: "risk_judge", vote: "PASS" },
    ],
    floorBlocks: [{ flag: "MEDICATION_NOT_IN_TRANSCRIPT", contract_type: "presence_check" }],
  };

  it("shows plain outcomes + reviewer names + readable flags, never raw codes", () => {
    render(<VerdictCard {...props} />);
    // outcomes
    expect(screen.getAllByText("Flagged").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Passed")).toBeInTheDocument();
    // reviewer names
    expect(screen.getByText("Faithfulness reviewer")).toBeInTheDocument();
    expect(screen.getByText("Risk reviewer")).toBeInTheDocument();
    // readable flag
    expect(screen.getByText("Medication not in transcript")).toBeInTheDocument();
    // NON-VACUOUS: the raw engine codes must NOT leak
    expect(screen.queryByText("BLOCK")).toBeNull();
    expect(screen.queryByText("faithfulness_judge")).toBeNull();
    expect(screen.queryByText("MEDICATION_NOT_IN_TRANSCRIPT")).toBeNull();
  });
});

describe("reviewerLabel (JUDGE-LABEL-1)", () => {
  it("prefers an SME-authored display name over the derived one", () => {
    expect(reviewerLabel({ judge_role: "openbio_reviewer", display_name: "Coverage reviewer" }))
      .toBe("Coverage reviewer");
  });

  it("falls back to the derived label when none is authored", () => {
    expect(reviewerLabel({ judge_role: "faithfulness_judge" })).toBe("Faithfulness reviewer");
    expect(reviewerLabel({ judge_role: "risk_judge", display_name: "" })).toBe("Risk reviewer");
    expect(reviewerLabel({ judge_role: "risk_judge", display_name: "   " })).toBe("Risk reviewer");
  });

  it("reads the role off either key shape the vote surfaces use", () => {
    expect(reviewerLabel({ role: "policy_judge" })).toBe("Policy reviewer");
  });

  it("never returns a raw id and survives a malformed vote", () => {
    expect(reviewerLabel({})).toBe("Reviewer");
    expect(reviewerLabel(null)).toBe("Reviewer");
  });
});
