/* JourneyApp.test.jsx — WS-7a verify-and-close (the D4 the parallel-session journey
   rework shipped without). Pins that Phase-2 "Verify" is wired to the live BFF grade:
   POST /v1/run-eval at the $0 replay default (A2), the real composite verdict renders
   (A1), "Run live" opts into a fresh in-process grade, and a BFF-down fetch degrades
   to the bundled fixture without crashing (A4). Mocks fetch — no network. */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { JourneyApp } from "./JourneyApp.jsx";

const PROPS = { theme: "dark", setTheme: () => {}, mode: "journey", setMode: () => {} };

// Center2 reads gradeResult.council.votes + gradeResult.result.verdict + .grade_path.
const RECORD = {
  grade_path: "replay",
  result: { verdict: "reject" },
  council: {
    votes: [
      { judge_role: "risk_judge", model: "gpt-4.1", vote: "BLOCK", confidence: "1.0", reason: "dose drift" },
      { judge_role: "policy_judge", model: "mistral", vote: "BLOCK", confidence: null, reason: "" },
      { judge_role: "faithfulness_judge", model: "llama", vote: "BLOCK", confidence: "0.97", reason: "" },
    ],
  },
};

// Branch fetch by URL: /v1/case fires on entering Act 2; /v1/run-eval on Verify.
function stubFetch(runEval) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url) => {
      const u = String(url);
      if (u.includes("/v1/case")) return Promise.resolve({ ok: true, json: () => Promise.resolve(null) });
      if (u.includes("/v1/run-eval")) return runEval();
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    }),
  );
}

async function gotoVerify() {
  render(<JourneyApp {...PROPS} />);
  fireEvent.keyDown(window, { key: "ArrowRight" }); // Act 1 → Act 2
  return screen.findByRole("button", { name: /verify \(replay/i });
}

describe("WS-7a — Journey Phase-2 'Verify' wired to the live BFF", () => {
  beforeEach(() => {
    // jsdom ships no matchMedia; jp2 reduced() needs it. matches:true skips the staged
    // reveal animation so the on-record verdict renders without the timer chain.
    window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} });
    // jsdom ships no Element.scrollTo; JourneyApp scrolls the convo on phase change.
    Element.prototype.scrollTo = () => {};
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("A1/A2 — Verify POSTs /v1/run-eval at the $0 replay default and renders the real verdict", async () => {
    stubFetch(() => Promise.resolve({ ok: true, json: () => Promise.resolve(RECORD) }));
    fireEvent.click(await gotoVerify());

    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes("/v1/run-eval"));
      expect(call).toBeTruthy();
      expect(JSON.parse(call[1].body)).toMatchObject({ agent: "ws0_default", live: false, in_process: false });
    });
    expect(await screen.findByText("REJECT")).toBeTruthy(); // the real composite verdict, not journeyData mock
  });

  it("A2 — 'Run live' opts into a fresh in-process grade (in_process:true; live stays false → never the paid :8002)", async () => {
    stubFetch(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ ...RECORD, grade_path: "in_process" }) }));
    render(<JourneyApp {...PROPS} />);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    fireEvent.click(await screen.findByRole("button", { name: /run live/i }));

    await waitFor(() => {
      const call = fetch.mock.calls.find(([u]) => String(u).includes("/v1/run-eval"));
      expect(call).toBeTruthy();
      expect(JSON.parse(call[1].body)).toMatchObject({ in_process: true, live: false });
    });
  });

  it("A4 — degrades gracefully when the BFF is down (no crash; bundled fixture)", async () => {
    stubFetch(() => Promise.reject(new Error("ECONNREFUSED")));
    fireEvent.click(await gotoVerify());
    expect(await screen.findByText(/BFF offline/i)).toBeTruthy();
  });
});
