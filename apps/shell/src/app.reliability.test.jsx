/* app.reliability.test.jsx — RELIABILITY-CARD-1 last-mile, the FULL real wiring: the ⌘K palette
   "Show reliability" action → the lithrim:show-reliability window bridge → CenterPane fetches
   GET /v1/reliability/{agent} → the tool-reliability_card renders INLINE. Mirrors app.cohort.test's
   end-to-end style over a fetch stub. Conversational-first: the card renders in the thread, no new
   tab; and the reliability trigger adds NO agent tool (the len(_TOOL_SPECS)==24 pin is pinned in
   pytest — this test only exercises the shell path). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./app.jsx";

const reliabilityCalls = (fetchSpy) =>
  fetchSpy.mock.calls.filter(([url]) => String(url).includes("/v1/reliability/"));

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url) => {
      const u = String(url);
      const body = u.includes("/v1/reliability/")
        ? {
            agent: "ws0_default",
            n_runs: 9,
            metrics: {
              n_runs: 9,
              inter_judge_kappa: { value: 0.71, n: 9 },
              selective_prediction: { coverage: { value: 0.44 }, conditional_accuracy: { value: 1.0 } },
            },
          }
        : {};
      return Promise.resolve({ ok: true, json: async () => body });
    }),
  );
});

const openPalette = () => fireEvent.keyDown(window, { key: "k", metaKey: true });

describe("RELIABILITY-CARD-1: the ⌘K 'Show reliability' trigger renders the card inline", () => {
  it("fetches the real reliability endpoint for the active agent and renders the tool-reliability_card", async () => {
    render(<App mode="shell" setMode={() => {}} />);
    openPalette();
    // /reliability metrics/ (not a bare /reliability/) — the palette also carries a "Reliability
    // sweep" entry (RIGOR-1 / Q1 — NEW-G3); this test targets the reliability-METRICS card.
    fireEvent.click(await screen.findByText(/reliability metrics/i));
    // the palette + bridge hit the REAL endpoint scoped to the active agent
    await waitFor(() => expect(reliabilityCalls(fetch).length).toBeGreaterThanOrEqual(1));
    expect(String(reliabilityCalls(fetch)[0][0])).toMatch(/\/v1\/reliability\/ws0_default/);
    // the card renders INLINE with the real value (no fabricated number)
    const card = await screen.findByTestId("reliability-card");
    expect(card.textContent).toMatch(/0\.71/);
  });
});
