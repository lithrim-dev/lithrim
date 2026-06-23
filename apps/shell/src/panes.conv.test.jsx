/* panes.conv.test.jsx — PERSIST-CONV: durable conversation persistence in CenterPane.

   The chat thread lived ONLY in CenterPane React state, keyed by a remount sessionKey, so a
   browser refresh wiped it. CenterPane now HYDRATES from GET /v1/conversation on mount /
   agent-change (getConversation → setChat) and PERSISTS the settled thread via
   PUT /v1/conversation (putConversation) after a turn. Mocks the whole bff.js surface (the
   panes.chat.test.jsx pattern) so the loop runs without a live BFF. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// vi.mock is hoisted above module scope, so the conversation spies live in vi.hoisted
// (the only state the factory may close over).
const { getConversation, putConversation } = vi.hoisted(() => ({
  getConversation: vi.fn(),
  putConversation: vi.fn(),
}));

vi.mock("./bff.js", () => ({
  runEval: vi.fn().mockResolvedValue({ composite: { verdict: "reject" }, council: { votes: [] } }),
  getRuns: vi.fn().mockResolvedValue({ runs: [] }),
  runEvalPack: vi.fn().mockResolvedValue({}),
  getCorpus: vi.fn().mockResolvedValue({ rows: [] }),
  getCase: vi.fn().mockResolvedValue({ case_id: "c", transcript: "…", expected_safety_flags: [] }),
  listCases: vi.fn().mockResolvedValue({ cases: [], count: 0 }),
  getOntology: vi.fn().mockResolvedValue({ flags: [], questions: [] }),
  putOntology: vi.fn().mockResolvedValue({}),
  getGroundingContractTypes: vi.fn().mockResolvedValue({ contract_types: ["presence_check"], pack: "_core" }),
  getAgent: vi.fn().mockResolvedValue({ name: "ws0_default", eval_profile: {} }),
  putAgent: vi.fn().mockResolvedValue({}),
  getAudit: vi.fn().mockResolvedValue({ records: [] }),
  getRunAudit: vi.fn().mockResolvedValue({}),
  getJudges: vi.fn().mockResolvedValue({ judges: [], roles: [], validators: [] }),
  getJudge: vi.fn().mockResolvedValue({
    role: "risk_judge", model: "", assigned_flags: [], available_flags: [],
    available_validators: [], validator_refs: [], questions: [], base_prompt: "", rendered_prompt: "",
  }),
  putJudge: vi.fn().mockResolvedValue({}),
  optimizeJudge: vi.fn().mockResolvedValue({}),
  // PERSIST-CONV: the durable-conversation pair under test.
  getConversation,
  putConversation,
  chatStream: vi.fn(async (_req, { onEvent } = {}) => {
    if (!onEvent) return;
    onEvent({ event: "assistant_delta", text: "Authoring the risk judge, then running a replay." });
    onEvent({ event: "done", cost_usd: 0, cost_label: "x" });
  }),
}));

import { CenterPane } from "./panes.jsx";

beforeEach(() => {
  getConversation.mockClear().mockResolvedValue({ agent: "ws0_default", thread: [] });
  putConversation.mockClear().mockResolvedValue({ ok: true });
});

const props = { onOpenArtifact: vi.fn(), artifactOpen: false, onRunEval: vi.fn(), runStatus: "idle" };

describe("CenterPane — PERSIST-CONV: durable conversation persistence", () => {
  it("A5: hydrates the stored thread from getConversation on mount (the refresh survives)", async () => {
    getConversation.mockResolvedValueOnce({
      agent: "ws0_default",
      thread: [
        { role: "user", text: "my domain is radiology" },
        { role: "assistant", text: "Got it — radiology it is.", parts: [] },
      ],
    });
    render(<CenterPane {...props} agent="ws0_default" />);

    // it asked the store for THIS agent's thread...
    await waitFor(() => expect(getConversation).toHaveBeenCalledWith("ws0_default"));
    // ...and rendered the hydrated turns (not the empty-state)
    expect(await screen.findByText("my domain is radiology")).toBeInTheDocument();
    expect(await screen.findByText(/radiology it is/)).toBeInTheDocument();
  });

  it("A6: re-hydrates for the agent on the prop (per-agent thread, not ws0_default)", async () => {
    render(<CenterPane {...props} agent="imported_X" />);
    await waitFor(() => expect(getConversation).toHaveBeenCalledWith("imported_X"));
  });

  it("A7: persists the settled thread via putConversation after a turn", async () => {
    render(<CenterPane {...props} agent="ws0_default" />);
    await waitFor(() => expect(getConversation).toHaveBeenCalled());

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "author a risk judge" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the turn streamed...
    expect(await screen.findByText(/Authoring the risk judge/)).toBeInTheDocument();
    // ...and once it settled the thread was persisted for this agent (the user + assistant turn)
    await waitFor(() => expect(putConversation).toHaveBeenCalled());
    const [agentArg, threadArg] = putConversation.mock.calls.at(-1);
    expect(agentArg).toBe("ws0_default");
    expect(threadArg.some((m) => m.role === "user" && m.text === "author a risk judge")).toBe(true);
    expect(threadArg.some((m) => m.role === "assistant")).toBe(true);
  });

  it("A8 (non-vacuous): an empty stored thread does NOT persist on mount (no clobber of nothing)", async () => {
    render(<CenterPane {...props} agent="ws0_default" />);
    await waitFor(() => expect(getConversation).toHaveBeenCalled());
    // a brand-new agent (empty thread, no turn taken) must not write an empty thread back
    expect(putConversation).not.toHaveBeenCalled();
    // and the clean empty-state shows
    expect(screen.getByText(/What do you want to evaluate\?/i)).toBeInTheDocument();
  });
});
