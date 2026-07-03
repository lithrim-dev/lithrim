/* app.costgate.test.jsx — S-BS-80: the TopBar "Run live" is a PAID action and must be
   cost-confirmed in-DOM (CostModal), never fired on a bare click. The composer/chat paid paths
   were already gated; this was the last one-click unconfirmed spend in the product. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./app.jsx";

const ranEval = (fetchSpy) =>
  fetchSpy.mock.calls.filter(([url]) => String(url).includes("/v1/run-eval"));

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url) => {
      const body = String(url).includes("/v1/run-eval")
        ? { composite: { verdict: "reject" }, council: { votes: [] }, case_id: "c1" }
        : {};
      return Promise.resolve({ ok: true, json: async () => body });
    }),
  );
});

describe("S-BS-80: TopBar Run live is cost-gated", () => {
  it("clicking Run live opens the cost confirm and fires NO paid run", async () => {
    render(<App mode="shell" setMode={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /run live/i }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toMatch(/paid/i);
    expect(ranEval(fetch)).toHaveLength(0);
  });

  it("confirming fires exactly one live run (live:true on the wire)", async () => {
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /run live/i }));
    fireEvent.click(await screen.findByRole("button", { name: /run live \(paid\)/i }));
    await waitFor(() => expect(ranEval(fetch)).toHaveLength(1));
    const [, init] = ranEval(fetch)[0];
    expect(String(init?.body || "")).toMatch(/"live"\s*:\s*true/);
    unmount();
  });

  it("cancelling fires nothing", async () => {
    render(<App mode="shell" setMode={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /run live/i }));
    fireEvent.click(await screen.findByRole("button", { name: /cancel/i }));
    expect(ranEval(fetch)).toHaveLength(0);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
