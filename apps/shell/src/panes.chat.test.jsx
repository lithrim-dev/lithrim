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
import { chatStream } from "./bff.js";

beforeEach(() => chatStream.mockClear());

describe("CenterPane — the R11 conversational loop", () => {
  it("streams a chat turn: user msg + assistant text + the verdict card render inline", async () => {
    render(<CenterPane onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} runStatus="idle" />);

    const ta = screen.getByPlaceholderText(/Ask Lithrim/i);
    fireEvent.change(ta, { target: { value: "Author a risk judge and run it" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(chatStream).toHaveBeenCalledTimes(1));
    expect(chatStream).toHaveBeenCalledWith(
      { message: "Author a risk judge and run it", agent: "ws0_default" },
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );

    // the user's message echoes
    expect(await screen.findByText("Author a risk judge and run it")).toBeInTheDocument();
    // the streamed assistant text renders
    expect(await screen.findByText(/Authoring the risk judge/)).toBeInTheDocument();
    // the tool-result renders the EXISTING verdict card (no new component) — REJECT shows
    expect(await screen.findByText("REJECT")).toBeInTheDocument();
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
