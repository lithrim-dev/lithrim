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
const { getConversation, putConversation, deleteConversation } = vi.hoisted(() => ({
  getConversation: vi.fn(),
  putConversation: vi.fn(),
  deleteConversation: vi.fn(),
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
  // PERSIST-CONV: the durable-conversation accessors under test.
  getConversation,
  putConversation,
  deleteConversation,
  // UI-LOGIN-1 / SESSION-MENU-1: LeftRail reads these for the session-menu affordance — stub them
  // so the whole-surface mock covers every export the mounted components import.
  hasStoredToken: vi.fn().mockReturnValue(false),
  logout: vi.fn(),
  signIn: vi.fn(),
  // CONNECT-AI-CONSOLIDATE-1: LeftRail statically imports ProviderSettings (2-section), which
  // imports these — stub so mounting the rail never reaches a real fetch.
  configProvider: vi.fn().mockResolvedValue({ ok: true, plane: "grading", provider: "openai", last_tested: "" }),
  getProviderStatus: vi.fn().mockResolvedValue({ planes: {} }),
  getModelCatalog: vi.fn().mockResolvedValue({ providers: { openai: [], anthropic: [], azure: { models: [], note: "" } } }),
  bindRole: vi.fn().mockResolvedValue({ ok: true }),
  getRoleBindings: vi.fn().mockResolvedValue({ roles: {}, connected_providers: [] }),
  getCouncilRoster: vi.fn().mockResolvedValue({ panel: [], reviewer_roster: null }),
  setCouncilRoster: vi.fn().mockResolvedValue({ status: "ok" }),
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
  deleteConversation.mockClear().mockResolvedValue({ ok: true, removed: true });
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

  it("A9: 'Clear conversation' clears the store (deleteConversation) and empties the thread", async () => {
    getConversation.mockResolvedValueOnce({
      agent: "ws0_default",
      thread: [
        { role: "user", text: "my domain is radiology" },
        { role: "assistant", text: "Got it — radiology it is.", parts: [] },
      ],
    });
    render(<CenterPane {...props} agent="ws0_default" />);
    // the thread hydrated...
    expect(await screen.findByText("my domain is radiology")).toBeInTheDocument();

    // ...arm the in-DOM confirm (no window.confirm — it freezes the renderer), then confirm
    fireEvent.click(screen.getByTitle(/Clear conversation/i));
    fireEvent.click(await screen.findByTestId("chat-clear-confirm"));

    // the durable store is cleared for THIS agent...
    await waitFor(() => expect(deleteConversation).toHaveBeenCalledWith("ws0_default"));
    // ...and the on-screen thread empties back to the clean empty-state
    await waitFor(() => expect(screen.queryByText("my domain is radiology")).not.toBeInTheDocument());
    expect(screen.getByText(/What do you want to evaluate\?/i)).toBeInTheDocument();
  });

  it("A10 (non-vacuous): the clear affordance is absent on an empty thread (nothing to clear)", async () => {
    render(<CenterPane {...props} agent="ws0_default" />);
    await waitFor(() => expect(getConversation).toHaveBeenCalled());
    expect(screen.queryByTitle(/Clear conversation/i)).not.toBeInTheDocument();
  });

  it("A11 (non-vacuous): an `agent` prop change WITHOUT a remount swaps the thread (no bleed)", async () => {
    // agent_A has a stored thread; agent_B has its OWN distinct thread.
    getConversation.mockImplementation((a) =>
      a === "agent_A"
        ? Promise.resolve({
            agent: a,
            thread: [
              { role: "user", text: "alpha question" },
              { role: "assistant", text: "alpha answer", parts: [] },
            ],
          })
        : Promise.resolve({
            agent: a,
            thread: [
              { role: "user", text: "beta question" },
              { role: "assistant", text: "beta answer", parts: [] },
            ],
          }),
    );

    // mount with A — A's thread hydrates
    const { rerender } = render(<CenterPane {...props} agent="agent_A" />);
    expect(await screen.findByText("alpha question")).toBeInTheDocument();

    // flip the active agent to B on the SAME instance (no sessionKey/remount), as the live
    // ws0_default→eval-1 auto-resolution does
    rerender(<CenterPane {...props} agent="agent_B" />);
    await waitFor(() => expect(getConversation).toHaveBeenCalledWith("agent_B"));

    // A's turns are gone (the reported bleed) and B's thread is now shown
    await waitFor(() => expect(screen.queryByText("alpha question")).not.toBeInTheDocument());
    expect(screen.queryByText("alpha answer")).not.toBeInTheDocument();
    expect(await screen.findByText("beta question")).toBeInTheDocument();
    expect(await screen.findByText("beta answer")).toBeInTheDocument();
  });

  it("A12 (non-vacuous): an `agent` change to an EMPTY thread clears the prior thread (the live ws0→eval bug)", async () => {
    // this is the exact reported live shape: the prior agent has a thread, the new one is empty.
    // Without the synchronous reset, the no-clobber guard never re-applies (the empty thread's
    // `if (thread.length)` is false), so the OLD thread would persist under the NEW agent.
    getConversation.mockImplementation((a) =>
      a === "ws0_default"
        ? Promise.resolve({
            agent: a,
            thread: [
              { role: "user", text: "seeded ws0 turn" },
              { role: "assistant", text: "seeded ws0 reply", parts: [] },
            ],
          })
        : Promise.resolve({ agent: a, thread: [] }),
    );

    const { rerender } = render(<CenterPane {...props} agent="ws0_default" />);
    expect(await screen.findByText("seeded ws0 turn")).toBeInTheDocument();

    rerender(<CenterPane {...props} agent="eval-1" />);
    await waitFor(() => expect(getConversation).toHaveBeenCalledWith("eval-1"));

    // the seeded ws0 thread is gone and eval-1's clean empty-state shows
    await waitFor(() => expect(screen.queryByText("seeded ws0 turn")).not.toBeInTheDocument());
    expect(screen.queryByText("seeded ws0 reply")).not.toBeInTheDocument();
    expect(screen.getByText(/What do you want to evaluate\?/i)).toBeInTheDocument();
  });
});
