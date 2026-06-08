/* panes.chat.test.jsx — UAP-5b / R11: the live conversational loop in CenterPane.
   The composer streams POST /v1/chat (mocked chatStream); each SSE event renders
   inline — assistant text + a tool-result gen-UI part (the EXISTING verdict card,
   no new component). Mocks the whole bff.js surface so the scripted cards mount
   without a live BFF. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("./bff.js", () => ({
  runEval: vi.fn().mockResolvedValue({ composite: { verdict: "reject" }, council: { votes: [] } }),
  getRuns: vi.fn().mockResolvedValue({ runs: [] }),
  runEvalPack: vi.fn().mockResolvedValue({}),
  getCorpus: vi.fn().mockResolvedValue({ rows: [] }),
  getOntology: vi.fn().mockResolvedValue({ flags: [], questions: [] }),
  putOntology: vi.fn().mockResolvedValue({}),
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
  // The loop under test: drive the onEvent callback with a scripted SSE stream.
  chatStream: vi.fn(async (_req, { onEvent } = {}) => {
    if (!onEvent) return;
    onEvent({ event: "assistant_delta", text: "Authoring the risk judge, then running a replay." });
    onEvent({
      event: "tool_result",
      part: {
        type: "tool-verdict_card",
        state: "output-available",
        output: { id: "run-1", verdict: "REJECT", confidence: "0.99", agreement: "3 / 3" },
      },
    });
    onEvent({ event: "done", cost_usd: 0.1, cost_label: "subscription-equivalent estimate" });
  }),
}));

import { CenterPane } from "./panes.jsx";
import App from "./app.jsx";
import { chatStream } from "./bff.js";

beforeEach(() => chatStream.mockClear());

describe("CenterPane — the R11 conversational loop", () => {
  it("streams a chat turn: user msg + assistant text + the verdict card render inline", async () => {
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "Author a risk judge and run it" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(1));
    // ONB-0: the first send carries an empty history (no prior turns yet).
    expect(chatStream).toHaveBeenCalledWith(
      { message: "Author a risk judge and run it", agent: "ws0_default", history: [] },
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );

    // the user's message echoes
    expect(await screen.findByText("Author a risk judge and run it")).toBeInTheDocument();
    // the streamed assistant text renders
    expect(await screen.findByText(/Authoring the risk judge/)).toBeInTheDocument();
    // the tool-result renders the EXISTING verdict card (no new component) — REJECT shows
    expect(await screen.findByText("REJECT")).toBeInTheDocument();
  });

  it("CHATBIND-1: threads the ACTIVE (rail-selected) agent into chatStream, not ws0_default", async () => {
    // The shell half of the active-agent binding (S-BS-103): CenterPane's `agent` prop comes
    // from app.jsx's activeAgent; send() must POST it so the BFF loop scopes to the selected
    // case. Regression guard — if the prop threading regresses to the ws0_default default,
    // the chat would review the wrong case (the live dogfooding symptom).
    render(<CenterPane agent="imported_X" onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "show + review this case" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(1));
    expect(chatStream).toHaveBeenCalledWith(
      { message: "show + review this case", agent: "imported_X", history: [] },
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );
  });

  it("streams the journey tool-parts and renders them inline via the existing registry (no new cards)", async () => {
    // UAP-5c: re-script the loop to stream the NEW journey cards as tool_result parts.
    // The chat pane renders them through the SAME type-agnostic renderTool path as the
    // verdict card above; per-type card rendering for all 9 tools is covered by
    // genui/registry.test.jsx. Here we assert the chat pane STREAMS a new journey part
    // and renders it inline — witnessed unambiguously by the audit_log card carrying the
    // streamed runId (the scripted-default audit_log has no run id, so it's chat-unique).
    chatStream.mockImplementationOnce(async (_req, { onEvent } = {}) => {
      if (!onEvent) return;
      onEvent({ event: "assistant_delta", text: "Reading the domain, editing a flag, reviewing runs." });
      onEvent({ event: "tool_result", part: { type: "tool-agent_editor", state: "output-available", output: { agent: "ws0_default" } } });
      onEvent({ event: "tool_result", part: { type: "tool-flag_editor", state: "output-available", output: { agent: "ws0_default" } } });
      onEvent({ event: "tool_result", part: { type: "tool-audit_log", state: "output-available", output: { runId: "run-1" } } });
      onEvent({ event: "done", cost_usd: 0, cost_label: "subscription-equivalent estimate" });
    });
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "Walk the whole journey from scratch" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // the chat streamed its narration, and the review_runs → audit_log part rendered the
    // EXISTING card inline carrying its streamed run id — none of the parts hit the fallback
    expect(await screen.findByText(/Reading the domain, editing a flag/)).toBeInTheDocument();
    expect(await screen.findByDisplayValue("run-1")).toBeInTheDocument();
    expect(screen.queryByText(/Unsupported component/)).toBeNull();
  });

  it("ONB-0: a 2nd send replays the prior turn as history (memory threads to the loop)", async () => {
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);

    // turn 1 — the default scripted stream yields assistant text "Authoring the risk judge…"
    fireEvent.change(ta, { target: { value: "my domain is radiology" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(1));
    await screen.findByText(/Authoring the risk judge/);

    // turn 2 — history must carry turn 1: the user msg + the streamed assistant text
    fireEvent.change(ta, { target: { value: "what did we just do?" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(2));

    const secondArgs = chatStream.mock.calls[1][0];
    expect(secondArgs.message).toBe("what did we just do?");
    expect(secondArgs.history).toEqual([
      { role: "user", content: "my domain is radiology" },
      { role: "assistant", content: "Authoring the risk judge, then running a replay." },
    ]);
  });

  it("opening the in-DOM cost modal exposes the human-only paid confirm (the agent cannot)", async () => {
    const onRunEval = vi.fn().mockResolvedValue();
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={onRunEval} runStatus="idle" />);

    // the cost gate is the human's; trigger the modal via the composer's paid affordance
    fireEvent.click(screen.getByTitle(/Run a live, paid evaluation/i));
    const confirm = await screen.findByTestId("cost-confirm");
    fireEvent.click(confirm);
    // confirm calls the EXISTING paid path (live=true) — the modal is the only door
    await waitFor(() => expect(onRunEval).toHaveBeenCalledWith(true));
  });
});

// UX-1 (S-BS-89): the chat surface defaults CLEAN — empty-state instead of the scripted
// 8-message preamble; the showcase is opt-in; "New evaluation" resets to a clean slate;
// live turns carry a neutral identity; cadence (auto-grow + autoscroll) is wired.
describe("CenterPane / Shell — UX-1: clean default + cadence + New-eval (S-BS-89)", () => {
  const props = { onOpenArtifact: vi.fn(), artifactOpen: false, onRunEval: vi.fn(), runStatus: "idle" };

  // revealing the opt-in showcase mounts the scripted FlagEditor, which self-fetches
  // GET /v1/ontology — stub fetch so the reveal is clean.
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ domain: "clinical", ontology_version: "clinical/1", severity_map: { block_at_or_above: 0.5, warn_above: 0, weights: {} }, flags: [] }),
      }),
    );
  });

  it("opens to a clean empty-state — no scripted demo content; 'Show example' reveals it", () => {
    render(<CenterPane {...props} />);
    // the real greeting is shown...
    expect(screen.getByText(/What do you want to evaluate\?/i)).toBeInTheDocument();
    // ...and NONE of the scripted preamble / fake header chips (A2)
    expect(screen.queryByText(/Scribe Agent v4/)).toBeNull();
    expect(screen.queryByText("Jordan")).toBeNull();
    expect(screen.queryByText(/2,400 samples/)).toBeNull();

    // opt-in reveals the canned showcase (preamble + the fake header chips)
    fireEvent.click(screen.getByText(/Show example conversation/i));
    expect(screen.getByText(/2,400 samples/)).toBeInTheDocument();
    expect(screen.getAllByText(/Scribe Agent v4/).length).toBeGreaterThan(0);
  });

  it("live turns use a neutral identity (You), never the scripted Jordan", async () => {
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "hello" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await screen.findByText(/Authoring the risk judge/);
    expect(screen.getAllByText("You").length).toBeGreaterThan(0);
    expect(screen.queryByText("Jordan")).toBeNull();
  });

  it("'New evaluation' resets the chat to a clean slate (App remounts CenterPane)", async () => {
    render(<App mode="shell" setMode={() => {}} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "reset me please" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    expect(await screen.findByText("reset me please")).toBeInTheDocument();

    fireEvent.click(screen.getByTitle("New evaluation"));
    // the live turn is gone and the empty-state is back
    expect(screen.queryByText("reset me please")).toBeNull();
    expect(screen.getByText(/What do you want to evaluate\?/i)).toBeInTheDocument();
  });

  it("composer auto-grows with input, capped at 200px", () => {
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    Object.defineProperty(ta, "scrollHeight", { configurable: true, value: 120 });
    fireEvent.change(ta, { target: { value: "a\nb\nc" } });
    expect(ta.style.height).toBe("120px");
    // grows up to the cap, then stops
    Object.defineProperty(ta, "scrollHeight", { configurable: true, value: 500 });
    fireEvent.change(ta, { target: { value: "a\nb\nc\nd\ne\nf\ng" } });
    expect(ta.style.height).toBe("200px");
  });

  it("autoscrolls to the latest turn on stream (scrollIntoView)", async () => {
    const spy = vi.spyOn(Element.prototype, "scrollIntoView");
    render(<CenterPane {...props} />);
    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "scroll me" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await screen.findByText(/Authoring the risk judge/);
    expect(spy).toHaveBeenCalled();
  });
});
