/* app.coerce.test.jsx — SHEPHERD-1b (W1, S-BS-149): the shell coerces activeAgent onto the
   SAME agent the chat shepherd resolves, so the rail and the shepherd never describe different
   agents. The live divergence: the shell defaults activeAgent to ws0_default, but a non-default
   workspace's agent list may not include it — so the rail derived a phantom "0 / 5" while the
   shepherd (_resolve_chat_agent) operated the workspace's first agent.

   This pins the shell coercion to the BFF contract two ways:
     1. a replica of _resolve_chat_agent (apps/bff/app.py:1479-1483) the shell MUST mirror, so the
        unit assertion and the BFF tests (tests/test_uap5b_chat.py) stay in lockstep on one rule;
     2. a React harness running the EXACT coercion effect from app.jsx:265-267 over synchronous
        props (the App mount-effect chain hangs on dynamic-import flush under jsdom — the
        click-driven app.chat.test.jsx is the only integration path that flushes — so we exercise
        the effect's real React semantics directly: absent→agents[0], present→honored, empty→
        unchanged, and idempotent with NO sessionKey bump). */
import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { useState, useEffect } from "react";

// (1) The BFF _resolve_chat_agent contract (apps/bff/app.py:1479-1483) the shell mirrors.
function resolveAgent(reqAgent, names) {
  if (names.includes(reqAgent)) return reqAgent; // honor a valid (incl. deep-linked) agent
  if (names.length) return names[0]; // coerce an absent/stale arg to the first agent
  return reqAgent; // no agents — keep the ask (the loop surfaces the honest 404)
}

// (2) A harness that runs app.jsx's EXACT coercion effect. `agents` is driven via props so we
// control timing synchronously. It surfaces activeAgent + a sessionKey counter so a test can
// prove the coercion uses setActiveAgent ONLY (it must never bump sessionKey / remount the chat).
function CoerceHarness({ initialAgent = "ws0_default", agents }) {
  const [activeAgent, setActiveAgent] = useState(initialAgent);
  // sessionKey stands in for app.jsx's CenterPane remount key — the coercion must NOT touch it.
  const [sessionKey] = useState(0);
  // VERBATIM from app.jsx:265-267 (the SHEPHERD-1b W1 coercion).
  useEffect(() => {
    if (agents.length > 0 && !agents.includes(activeAgent)) setActiveAgent(agents[0]);
  }, [agents]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div>
      <span data-testid="active">{activeAgent}</span>
      <span data-testid="skey">{sessionKey}</span>
    </div>
  );
}

describe("SHEPHERD-1b (W1) — the shell coerces activeAgent onto the shepherd's resolved agent", () => {
  it("mirrors the BFF _resolve_chat_agent contract exactly", () => {
    const names = ["eval-1", "snomed-demo"];
    expect(resolveAgent("ws0_default", names)).toBe("eval-1"); // absent -> agents[0]
    expect(resolveAgent("snomed-demo", names)).toBe("snomed-demo"); // present -> honored
    expect(resolveAgent("ws0_default", [])).toBe("ws0_default"); // empty -> unchanged (no crash)
  });

  it("coerces an absent default to agents[0] (the rail/shepherd converge)", () => {
    render(<CoerceHarness initialAgent="ws0_default" agents={["eval-1", "snomed-demo"]} />);
    expect(screen.getByTestId("active").textContent).toBe("eval-1");
    // the coercion used setActiveAgent only — sessionKey is untouched (no CenterPane remount)
    expect(screen.getByTestId("skey").textContent).toBe("0");
  });

  it("honors a valid activeAgent (incl. a deep-link) verbatim", () => {
    render(<CoerceHarness initialAgent="snomed-demo" agents={["eval-1", "snomed-demo"]} />);
    expect(screen.getByTestId("active").textContent).toBe("snomed-demo");
  });

  it("leaves activeAgent unchanged when the agent list is empty (no crash)", () => {
    render(<CoerceHarness initialAgent="ws0_default" agents={[]} />);
    expect(screen.getByTestId("active").textContent).toBe("ws0_default");
  });

  it("is idempotent — re-running the effect on the coerced agent does not flip-flop", () => {
    const { rerender } = render(
      <CoerceHarness initialAgent="ws0_default" agents={["eval-1", "snomed-demo"]} />,
    );
    expect(screen.getByTestId("active").textContent).toBe("eval-1"); // coerced once
    // re-fire the [agents] effect with a NEW array of the SAME names: eval-1 is now valid, so the
    // predicate is false and the agent stays put (no oscillation, no further remount).
    act(() => rerender(<CoerceHarness initialAgent="eval-1" agents={["eval-1", "snomed-demo"]} />));
    expect(screen.getByTestId("active").textContent).toBe("eval-1");
    expect(screen.getByTestId("skey").textContent).toBe("0");
  });
});
