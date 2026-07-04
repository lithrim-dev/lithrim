/* panes.reliability.test.jsx — RELIABILITY-CARD-1 last-mile: the reliability card needs a
   user-reachable TRIGGER. RELIABILITY-CARD-1 shipped GET /v1/reliability/{agent} + the
   tool-reliability_card genui card + bff.js getReliability, but NOTHING emitted/rendered it —
   a user couldn't see it. The fix mirrors COHORT-SUBSET-1: a ⌘K palette entry dispatches the
   `lithrim:show-reliability` window bridge; CenterPane fetches the REAL endpoint (getReliability
   over the active agent) and appends an assistant turn rendering the tool-reliability_card part
   INLINE (conversational-first — no new tab/chrome, no 25th agent tool). On an endpoint error the
   card's honest empty/insufficient state shows — never a fabricated number, never a crash. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";

vi.mock("./bff.js", () => ({
  runEval: vi.fn().mockResolvedValue({}),
  gradeCases: vi.fn().mockResolvedValue({}),
  getReliability: vi.fn(),
  getConversation: vi.fn().mockResolvedValue({ agent: "ws0_default", thread: [] }),
  putConversation: vi.fn().mockResolvedValue({ ok: true }),
  deleteConversation: vi.fn().mockResolvedValue({ ok: true, removed: false }),
  hasStoredToken: vi.fn().mockReturnValue(false),
  logout: vi.fn(),
  signIn: vi.fn(),
  ingestPreview: vi.fn().mockResolvedValue({}),
  getRoleBindings: vi.fn().mockResolvedValue({ chat_ready: true, roles: {}, connected_providers: [] }),
  chatStream: vi.fn(async () => {}),
}));

import { CenterPane } from "./panes.jsx";
import { getReliability } from "./bff.js";

beforeEach(() => { getReliability.mockReset(); });

const dispatchShow = () =>
  act(() => { window.dispatchEvent(new CustomEvent("lithrim:show-reliability")); });

const mount = (agent = "ws0_default") =>
  render(
    <CenterPane agent={agent} activeCase={null} onActiveCase={vi.fn()}
      onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
  );

describe("CenterPane — RELIABILITY-CARD-1: the palette 'Show reliability' trigger", () => {
  it("HEADLINE: the bridge fetches getReliability(activeAgent) and renders the card INLINE with the REAL metrics", async () => {
    // a real endpoint payload: {agent, metrics, n_runs}. The card reads the flat-spread metrics.
    getReliability.mockResolvedValueOnce({
      agent: "ws0_default",
      n_runs: 12,
      metrics: {
        n_runs: 12,
        inter_judge_kappa: { value: 0.62, n: 12 },
        cohen_kappa_vs_gold: { insufficient: true, reason: "no gold" },
        selective_prediction: { coverage: { value: 0.5 }, conditional_accuracy: { value: 1.0 } },
      },
    });
    mount("ws0_default");
    dispatchShow();
    // fetched the REAL endpoint scoped to the ACTIVE agent
    await waitFor(() => expect(getReliability).toHaveBeenCalledWith("ws0_default"));
    // rendered the tool-reliability_card INLINE (the registry card, bound to the real payload)
    const card = await screen.findByTestId("reliability-card");
    expect(card).toBeInTheDocument();
    // the real value tile is present (no fabricated number)
    expect(card.textContent).toMatch(/0\.62/);
    expect(card.textContent).toMatch(/12 runs/);
  });

  it("HONEST FAILURE: an endpoint error renders the card's empty/insufficient state — no crash, no fake data", async () => {
    getReliability.mockRejectedValueOnce(new Error("404 not found"));
    mount("ws0_default");
    dispatchShow();
    await waitFor(() => expect(getReliability).toHaveBeenCalledWith("ws0_default"));
    // the card still renders honestly (its no-metrics empty state), never a fabricated value
    const card = await screen.findByTestId("reliability-card");
    expect(card.textContent).toMatch(/No graded runs yet|not enough data/i);
    // no NaN / fabricated number leaked
    expect(card.textContent).not.toMatch(/NaN/);
  });
});
