/* panes.test.jsx — A4 / S-BS-19: the scripted Shell host (CenterPane) mounts the 3
   input tool-parts and threads each widget's onResult into local config-plane state. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CenterPane } from "./panes.jsx";

// FlagEditor (mounted inside CenterPane) self-fetches GET /v1/ontology — stub fetch.
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ domain: "clinical", ontology_version: "clinical/1", severity_map: { block_at_or_above: 0.5, warn_above: 0, weights: {} }, flags: [] }),
    }),
  );
});

const props = { onOpenArtifact: () => {}, artifactOpen: true, onRunEval: () => {}, runStatus: "idle" };

describe("CenterPane host mounts input tool-parts (S-BS-19)", () => {
  it("mounts FlagEditor + ContractBuilder + KbPicker", async () => {
    render(<CenterPane {...props} />);
    // S-BS-89: the scripted showcase is opt-in now — reveal it before asserting its widgets.
    fireEvent.click(screen.getByText(/Show example conversation/i));
    // each widget identified by its unique action button (FlagEditor after its GET resolves).
    expect(await screen.findByRole("button", { name: /Persist draft/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add contract/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Bind KB/i })).toBeInTheDocument();
    expect(screen.getByText(/Saved so far:/)).toBeInTheDocument();
    expect(screen.getByText("nothing yet")).toBeInTheDocument();
  });

  it("ACTIVE-CASE-1: names the active case in the header chrome (it is visible, not hidden)", () => {
    render(<CenterPane {...props} agent="ws0_default" activeCase="clinical_scribe_10_splinter_injury_vaccine_refusal" onActiveCase={() => {}} />);
    // the case the agent's "this case" resolves to is shown on screen — no hidden referent.
    expect(screen.getByText(/clinical_scribe_10_splinter/)).toBeInTheDocument();
  });

  it("ACTIVE-CASE-1: shows 'No case selected' when none is active (no silent first-case default)", () => {
    render(<CenterPane {...props} agent="ws0_default" activeCase={null} onActiveCase={() => {}} />);
    expect(screen.getByText(/No case selected/i)).toBeInTheDocument();
  });

  it("threads a widget's onResult into config-plane state", async () => {
    render(<CenterPane {...props} />);
    fireEvent.click(screen.getByText(/Show example conversation/i)); // S-BS-89: reveal the opt-in showcase
    // KbPicker binds namespaces by default → "Bind KB" is enabled; its onResult captures "kb".
    fireEvent.click(screen.getByRole("button", { name: /Bind KB/i }));
    await waitFor(() => expect(screen.getByText("kb")).toBeInTheDocument());
  });

  // UAP-5a D1 (S-BS-62): the JudgeEditor must render IN the conversation — before
  // this phase tool-judge_editor was registered but mounted nowhere, so a user could
  // not author a judge in the shell (the assignment had to go through curl).
  it("mounts the JudgeEditor with the $0 prompt preview (S-BS-62)", async () => {
    render(<CenterPane {...props} />);
    fireEvent.click(screen.getByText(/Show example conversation/i)); // S-BS-89: reveal the opt-in showcase
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    // the live $0 prompt-preview surface (the assignment→prompt bridge, no model call) +
    // PROMPT-EDIT-1: the SME-editable reviewer prompt mounts alongside it
    expect(screen.getByText(/Rendered prompt preview/)).toBeInTheDocument();
    expect(screen.getByTestId("je-role-prompt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save judge/i })).toBeInTheDocument();
  });
});
