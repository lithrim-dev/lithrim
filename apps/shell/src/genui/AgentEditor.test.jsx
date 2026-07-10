/* AgentEditor.test.jsx — UAP-1 R1: the config-plane write surface loads an Agent via
   GET /v1/agent and PUTs the assembled edit through bff.js (the SME handle on X-Actor).
   Mocks bff.js (no live BFF) — guards the React side the Python round-trip doesn't. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  getAgent: vi.fn().mockResolvedValue({
    name: "ws0_default",
    eval_profile: {
      judges: ["risk_judge", "policy_judge"],
      council_config: { disposition: "compose-over-live-v2" },
      ontology_ref: "clinical_v1",
      ontology_path: "data/ontology/clinical_v1.json",
      tools: ["presence_check"],
      kb_bindings: {},
      severity_map_ref: "clinical_v1",
    },
    dataset: { case_id: "c", source: "s", baseline: "b", mode: "replay" },
  }),
  putAgent: vi.fn().mockResolvedValue({ status: "ok", name: "ws0_default", actor: { type: "user", id: "sme@acme" } }),
}));

import AgentEditor from "./AgentEditor.jsx";
import { getAgent, putAgent } from "../bff.js";

beforeEach(() => {
  getAgent.mockClear();
  putAgent.mockClear();
});

describe("AgentEditor (tool-agent_editor)", () => {
  it("loads the agent via GET and PUTs the assembled edit with the SME handle", async () => {
    const onResult = vi.fn();
    render(<AgentEditor onResult={onResult} />);

    expect(await screen.findByText(/Agent · ws0_default/)).toBeInTheDocument();
    expect(getAgent).toHaveBeenCalledTimes(1);

    // edit the roster + tools, attribute the write, save
    fireEvent.change(screen.getByLabelText(/Reviewers/i), {
      target: { value: "risk_judge, policy_judge, faithfulness_judge" },
    });
    fireEvent.change(screen.getByLabelText(/Fact-checks/i), { target: { value: "dosage_grounding" } });
    fireEvent.change(screen.getByLabelText(/Your name/i), { target: { value: "sme@acme" } });
    fireEvent.change(screen.getByLabelText(/Reason/i), { target: { value: "add faithfulness" } });
    fireEvent.click(screen.getByRole("button", { name: /Save agent/i }));

    await waitFor(() => expect(putAgent).toHaveBeenCalledTimes(1));
    const [body, opts] = putAgent.mock.calls[0];
    // the full Agent round-trips (merged, not partial — so agent_from_dict validates)
    expect(body.name).toBe("ws0_default");
    expect(body.eval_profile.judges).toEqual(["risk_judge", "policy_judge", "faithfulness_judge"]);
    expect(body.eval_profile.tools).toEqual(["dosage_grounding"]);
    expect(body.eval_profile.ontology_ref).toBe("clinical_v1");
    // the §2B who/why ride the call
    expect(opts).toMatchObject({ actor: "sme@acme", rationale: "add faithfulness" });
    // onResult threads the saved config into setup state
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(1));
  });

  it("falls back to the dev-default (no handle) — never blocks the write", async () => {
    render(<AgentEditor />);
    expect(await screen.findByText(/Agent · ws0_default/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Save agent/i }));
    await waitFor(() => expect(putAgent).toHaveBeenCalledTimes(1));
    const [, opts] = putAgent.mock.calls[0];
    expect(opts.actor).toBeUndefined(); // bff.js omits X-Actor → BFF dev-default attributes
  });
});
