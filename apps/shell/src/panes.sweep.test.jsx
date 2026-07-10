/* panes.sweep.test.jsx — RIGOR-1 / Q1 (NEW-G3): the reliability SWEEP card needs a user-reachable
   TRIGGER. Mirrors panes.reliability.test.jsx exactly: a `lithrim:show-sweep` window bridge (the
   same CustomEvent idiom as lithrim:show-reliability) → CenterPane fetches the REAL sweep endpoint
   (getReliabilitySweep over the active agent) and appends an assistant turn rendering the
   tool-sweep_card part INLINE (conversational-first — no new tab/chrome, NO 25th agent tool). On an
   endpoint error the card's honest empty state shows — never a fabricated number, never a crash. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";

vi.mock("./bff.js", () => ({
  runEval: vi.fn().mockResolvedValue({}),
  gradeCases: vi.fn().mockResolvedValue({}),
  getReliability: vi.fn(),
  getReliabilitySweep: vi.fn(),
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
import { getReliabilitySweep } from "./bff.js";

beforeEach(() => { getReliabilitySweep.mockReset(); });

const dispatchSweep = (detail) =>
  act(() => { window.dispatchEvent(new CustomEvent("lithrim:show-sweep", detail ? { detail } : undefined)); });

const mount = (agent = "ws0_default") =>
  render(
    <CenterPane agent={agent} activeCase={null} onActiveCase={vi.fn()}
      onOpenArtifact={vi.fn()} artifactOpen={false} onRunEval={vi.fn()} onRunResult={vi.fn()} runStatus="idle" />,
  );

describe("CenterPane — the 'Reliability sweep' trigger", () => {
  it("HEADLINE: the bridge fetches getReliabilitySweep(activeAgent) and renders the sweep card INLINE with the REAL curve", async () => {
    getReliabilitySweep.mockResolvedValueOnce({
      agent: "ws0_default",
      sweep: {
        insufficient: false,
        k_max: 5,
        series: [
          { k: 1, flip_rate: { value: 0.5, n: 2, ci: [0.1, 0.9] }, majority_convergence: { value: 0.5, n: 2 }, variance: { value: 0.2, n: 2 } },
          { k: 5, flip_rate: { value: 0.0, n: 2, ci: [0.0, 0.4] }, majority_convergence: { value: 1.0, n: 2 }, variance: { value: 0.1, n: 2 } },
        ],
      },
    });
    mount("ws0_default");
    dispatchSweep();
    // fetched the REAL endpoint scoped to the ACTIVE agent
    await waitFor(() => expect(getReliabilitySweep).toHaveBeenCalledWith("ws0_default", expect.anything()));
    // rendered the tool-sweep_card INLINE (the registry card, bound to the real payload)
    const card = await screen.findByTestId("sweep-card");
    expect(card).toBeInTheDocument();
    // the real flip-rate value is present (no fabricated number)
    expect(card.textContent).toMatch(/50%|0\.5/);
  });

  it("HONEST FAILURE: an endpoint error renders the card's empty/insufficient state — no crash, no fake data", async () => {
    getReliabilitySweep.mockRejectedValueOnce(new Error("404 not found"));
    mount("ws0_default");
    dispatchSweep();
    await waitFor(() => expect(getReliabilitySweep).toHaveBeenCalledWith("ws0_default", expect.anything()));
    const card = await screen.findByTestId("sweep-card");
    expect(card.textContent).toMatch(/No sampled runs yet|not enough data/i);
    expect(card.textContent).not.toMatch(/NaN/);
  });
});
