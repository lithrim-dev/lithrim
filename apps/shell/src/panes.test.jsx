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
    // each widget identified by its unique action button (FlagEditor after its GET resolves).
    expect(await screen.findByRole("button", { name: /Persist draft/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add contract/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Bind KB/i })).toBeInTheDocument();
    expect(screen.getByText(/Config plane captured:/)).toBeInTheDocument();
    expect(screen.getByText("nothing yet")).toBeInTheDocument();
  });

  it("threads a widget's onResult into config-plane state", async () => {
    render(<CenterPane {...props} />);
    // KbPicker binds namespaces by default → "Bind KB" is enabled; its onResult captures "kb".
    fireEvent.click(screen.getByRole("button", { name: /Bind KB/i }));
    await waitFor(() => expect(screen.getByText("kb")).toBeInTheDocument());
  });

  // UAP-5a D1 (S-BS-62): the JudgeEditor must render IN the conversation — before
  // this phase tool-judge_editor was registered but mounted nowhere, so a user could
  // not author a judge in the shell (the assignment had to go through curl).
  it("mounts the JudgeEditor with the $0 prompt preview (S-BS-62)", async () => {
    render(<CenterPane {...props} />);
    expect(await screen.findByText(/Judge · risk_judge/)).toBeInTheDocument();
    // the live $0 prompt-preview surface (the assignment→prompt bridge, no model call)
    expect(screen.getByText(/the exact role_key_questions/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save judge/i })).toBeInTheDocument();
  });
});
