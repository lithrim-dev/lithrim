/* app.sweep.test.jsx — RIGOR-1 / Q1 (NEW-G3), the FULL real wiring: the ⌘K palette "Reliability
   sweep" action → the lithrim:show-sweep window bridge → CenterPane fetches GET
   /v1/reliability/{agent}/sweep → the tool-sweep_card renders INLINE. Mirrors app.reliability.test
   end-to-end over a fetch stub. Conversational-first: the card renders in the thread, no new tab;
   the sweep trigger adds NO agent tool (the len(_TOOL_SPECS)==24 pin is unaffected — this is a
   shell-emitted window-bridge action). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./app.jsx";

const sweepCalls = (fetchSpy) =>
  fetchSpy.mock.calls.filter(([url]) => String(url).includes("/v1/reliability/") && String(url).includes("/sweep"));

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url) => {
      const u = String(url);
      const body = u.includes("/sweep")
        ? {
            agent: "ws0_default",
            n_cases: 2,
            sweep: {
              insufficient: false,
              k_max: 5,
              series: [
                { k: 1, flip_rate: { value: 0.5, n: 2, ci: [0.1, 0.9] }, majority_convergence: { value: 0.5, n: 2 }, variance: { value: 0.2, n: 2 } },
                { k: 5, flip_rate: { value: 0.0, n: 2, ci: [0.0, 0.4] }, majority_convergence: { value: 1.0, n: 2 }, variance: { value: 0.05, n: 2 } },
              ],
            },
          }
        : {};
      return Promise.resolve({ ok: true, json: async () => body });
    }),
  );
});

const openPalette = () => fireEvent.keyDown(window, { key: "k", metaKey: true });

describe("NEW-G3: the ⌘K 'Reliability sweep' trigger renders the sweep card inline", () => {
  it("fetches the real /sweep endpoint for the active agent and renders the tool-sweep_card", async () => {
    render(<App mode="shell" setMode={() => {}} />);
    openPalette();
    fireEvent.click(await screen.findByText(/reliability sweep/i));
    // the palette + bridge hit the REAL sweep endpoint scoped to the active agent
    await waitFor(() => expect(sweepCalls(fetch).length).toBeGreaterThanOrEqual(1));
    expect(String(sweepCalls(fetch)[0][0])).toMatch(/\/v1\/reliability\/ws0_default\/sweep/);
    // the card renders INLINE with the real curve (no fabricated number)
    const card = await screen.findByTestId("sweep-card");
    expect(card.textContent).toMatch(/50%|0\.5/);
  });
});
