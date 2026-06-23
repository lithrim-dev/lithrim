/* session_menu.test.jsx — SESSION-MENU-1: an always-on session control in the rail footer.

   Today BFF login is REACTIVE-only (shows on a 401) and the Sign-out button hides whenever no
   token is stored — so on an open/local server (the default) there is NO way to proactively sign
   in or out, and the rail-footer "⋯" is a dead button. This adds a small always-present session
   MENU (Sign in… / Sign out) to the LeftRail footer, plus a cancelable LoginScreen so a proactive
   sign-in on an open server isn't a dead-end.

   The LeftRail now imports `signIn` from bff.js (alongside hasStoredToken/logout); mock the whole
   bff surface and toggle hasStoredToken per test. G uses the REAL signIn (vi.importActual) to
   prove it dispatches the gate event AuthGate already listens for. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

const { hasStoredToken, logout, signIn } = vi.hoisted(() => ({
  hasStoredToken: vi.fn(),
  logout: vi.fn(),
  signIn: vi.fn(),
}));

vi.mock("./bff.js", () => ({ hasStoredToken, logout, signIn }));

import { LeftRail } from "./panes.jsx";
import { AuthGate, LoginScreen } from "./auth.jsx";

const AUTH_EVENT = "lithrim:auth-required";
const rail = { width: 270, agents: ["ws0_default"], activeAgent: "ws0_default" };

beforeEach(() => {
  hasStoredToken.mockReset().mockReturnValue(false);
  logout.mockReset();
  signIn.mockReset();
});

describe("LeftRail — SESSION-MENU-1: an always-on session control", () => {
  it("A: the session-menu trigger is ALWAYS present (signed out)", () => {
    hasStoredToken.mockReturnValue(false);
    render(<LeftRail {...rail} />);
    expect(screen.getByLabelText("Session menu")).toBeInTheDocument();
  });

  it("A: the session-menu trigger is ALWAYS present (signed in)", () => {
    hasStoredToken.mockReturnValue(true);
    render(<LeftRail {...rail} />);
    expect(screen.getByLabelText("Session menu")).toBeInTheDocument();
    // the ambiguous standalone key-button is gone (folded into the menu)
    expect(screen.queryByLabelText("Sign out")).toBeNull();
  });

  it("B: clicking the trigger opens the menu (status line + an action item appear)", () => {
    hasStoredToken.mockReturnValue(false);
    render(<LeftRail {...rail} />);
    // closed by default — no status line / action item yet
    expect(screen.queryByText(/Not signed in/i)).toBeNull();
    fireEvent.click(screen.getByLabelText("Session menu"));
    expect(screen.getByText(/Not signed in/i)).toBeInTheDocument();
    expect(screen.getByText(/Sign in/i)).toBeInTheDocument();
  });

  it("C: NOT authed — the menu shows 'Sign in…' and clicking it calls signIn", () => {
    hasStoredToken.mockReturnValue(false);
    render(<LeftRail {...rail} />);
    fireEvent.click(screen.getByLabelText("Session menu"));
    const item = screen.getByText(/Sign in/i);
    expect(item).toBeInTheDocument();
    fireEvent.click(item);
    expect(signIn).toHaveBeenCalled();
    expect(logout).not.toHaveBeenCalled();
    // the action closes the menu
    expect(screen.queryByText(/Not signed in/i)).toBeNull();
  });

  it("D: authed — the menu shows 'Sign out' and clicking it calls logout", () => {
    hasStoredToken.mockReturnValue(true);
    render(<LeftRail {...rail} />);
    fireEvent.click(screen.getByLabelText("Session menu"));
    expect(screen.getByText(/Signed in with an access token/i)).toBeInTheDocument();
    const item = screen.getByText("Sign out");
    fireEvent.click(item);
    expect(logout).toHaveBeenCalled();
    expect(signIn).not.toHaveBeenCalled();
    expect(screen.queryByText(/Signed in with an access token/i)).toBeNull();
  });

  it("E: clicking the backdrop closes the menu", () => {
    hasStoredToken.mockReturnValue(false);
    render(<LeftRail {...rail} />);
    fireEvent.click(screen.getByLabelText("Session menu"));
    expect(screen.getByText(/Not signed in/i)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("session-menu-backdrop"));
    expect(screen.queryByText(/Not signed in/i)).toBeNull();
  });
});

describe("LoginScreen / AuthGate — SESSION-MENU-1 (F): a cancelable proactive sign-in", () => {
  it("F: LoginScreen renders a cancel affordance and clicking it calls onCancel", () => {
    const onCancel = vi.fn();
    render(<LoginScreen onSuccess={vi.fn()} onCancel={onCancel} />);
    const cancel = screen.getByTestId("auth-cancel");
    expect(cancel).toBeInTheDocument();
    fireEvent.click(cancel);
    expect(onCancel).toHaveBeenCalled();
  });

  it("F: AuthGate's cancel dismisses the gate — children render again after a gate event + cancel", async () => {
    render(
      <AuthGate>
        <div data-testid="the-app">the product</div>
      </AuthGate>,
    );
    // a proactive sign-in raises the gate (the same event signIn dispatches)
    act(() => window.dispatchEvent(new Event(AUTH_EVENT)));
    expect(await screen.findByTestId("auth-token-input")).toBeInTheDocument();
    // cancel returns to the app — the open-server sign-in is no longer a dead-end
    fireEvent.click(screen.getByTestId("auth-cancel"));
    expect(await screen.findByTestId("the-app")).toBeInTheDocument();
    expect(screen.queryByTestId("auth-token-input")).toBeNull();
  });
});

describe("bff.signIn — SESSION-MENU-1 (G): dispatches the gate event", () => {
  it("G: signIn() dispatches lithrim:auth-required (the AuthGate trigger)", async () => {
    // the REAL signIn (this file mocks bff.js for the LeftRail tests above)
    const { signIn: realSignIn } = await vi.importActual("./bff.js");
    const spy = vi.fn();
    window.addEventListener(AUTH_EVENT, spy);
    realSignIn();
    window.removeEventListener(AUTH_EVENT, spy);
    expect(spy).toHaveBeenCalled();
  });
});
