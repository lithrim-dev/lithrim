/* panes.connectcta.test.jsx — FIRST-CONTACT-1: the empty state's "Connect AI" signpost.

   A fresh Docker boot has no chat provider and no SDK path — the first thing the empty state
   funnels the user into (chat) would fail. /v1/roles/bindings now carries `chat_ready`; when it
   is false the empty state renders a connect-the-assistant CTA whose click opens the LeftRail's
   Connect AI modal via the `lithrim:connect-ai` window event. Real bff.js over a URL-keyed
   fetch stub (the panes.test.jsx pattern). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { CenterPane, LeftRail } from "./panes.jsx";

function stubFetch({ chatReady }) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url) => {
      const u = String(url);
      if (u.includes("/v1/roles/bindings"))
        return Promise.resolve({
          ok: true,
          json: async () => ({ roles: {}, connected_providers: [], chat_ready: chatReady }),
        });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }),
  );
}

const props = { onOpenArtifact: () => {}, artifactOpen: false, onRunEval: () => {}, runStatus: "idle" };

describe("FIRST-CONTACT-1: connect-the-assistant signpost", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("chat_ready:false → the empty state renders the CTA and its click asks for Connect AI", async () => {
    stubFetch({ chatReady: false });
    const opened = vi.fn();
    window.addEventListener("lithrim:connect-ai", opened);
    render(<CenterPane {...props} />);
    const cta = await screen.findByTestId("connect-assistant-cta");
    expect(cta.textContent).toMatch(/assistant isn't connected/i);
    fireEvent.click(screen.getByRole("button", { name: /connect ai/i }));
    expect(opened).toHaveBeenCalledTimes(1);
    window.removeEventListener("lithrim:connect-ai", opened);
  });

  it("chat_ready:true → no CTA (an env-configured chat must not see a false banner)", async () => {
    stubFetch({ chatReady: true });
    render(<CenterPane {...props} />);
    await waitFor(() => expect(screen.getByTestId("start-guided-setup")).toBeTruthy());
    expect(screen.queryByTestId("connect-assistant-cta")).toBeNull();
  });

  it("the LeftRail opens the Connect AI modal on the window event", async () => {
    stubFetch({ chatReady: false });
    render(<LeftRail width={240} agents={[]} activeAgent="ws0_default" onSwitchAgent={() => {}} onDeleteAgent={() => {}} onNewEval={() => {}} />);
    expect(screen.queryByTestId("connect-ai-panel")).toBeNull();
    act(() => { window.dispatchEvent(new CustomEvent("lithrim:connect-ai")); });
    await screen.findByTestId("connect-ai-panel");
  });
});
