/* auth.test.jsx — UI-LOGIN-1: the runtime BFF login/logout gate.

   The BFF auth token is a CLIENT credential (no backend source-of-truth), so it lives in
   localStorage and is entered/cleared from the UI — not baked into the JS bundle. The gate
   is REACTIVE: it shows only when a `window` "lithrim:auth-required" event fires (raised on a
   401). With the server gate OFF (the local default) no 401 ever fires, so the gate never
   shows — the zero-friction default is preserved. jsdom provides a real localStorage, so the
   token helpers are tested directly. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";

// The token helpers + the validate/logout signals live in bff.js — mock only validateToken
// (it would otherwise fetch), keep the real localStorage-backed helpers under test.
const { validateToken } = vi.hoisted(() => ({ validateToken: vi.fn() }));
vi.mock("./bff.js", async (orig) => {
  const real = await orig();
  return { ...real, validateToken };
});

import { AuthGate, LoginScreen } from "./auth.jsx";
import { getToken, setToken, clearToken, hasStoredToken, logout } from "./bff.js";

beforeEach(() => {
  localStorage.clear();
  validateToken.mockReset();
});

const AUTH_EVENT = "lithrim:auth-required";

describe("AuthGate — UI-LOGIN-1 (A/B): reactive gate, default-off is zero-friction", () => {
  it("A: renders its children by default — no login screen until a 401 fires", () => {
    render(
      <AuthGate>
        <div data-testid="the-app">the product</div>
      </AuthGate>,
    );
    expect(screen.getByTestId("the-app")).toBeInTheDocument();
    // the pre-auth screen is absent on the zero-friction default
    expect(screen.queryByTestId("auth-token-input")).toBeNull();
  });

  it("B: a `lithrim:auth-required` event shows the LoginScreen (the token input appears)", async () => {
    render(
      <AuthGate>
        <div data-testid="the-app">the product</div>
      </AuthGate>,
    );
    act(() => {
      window.dispatchEvent(new Event(AUTH_EVENT));
    });
    // the pre-auth screen replaced the app
    expect(await screen.findByTestId("auth-token-input")).toBeInTheDocument();
    expect(screen.queryByTestId("the-app")).toBeNull();
  });
});

describe("LoginScreen — UI-LOGIN-1 (C): valid stores + dismisses, invalid errors + does not store", () => {
  it("C(valid): a validated token is stored and onSuccess dismisses the gate", async () => {
    validateToken.mockResolvedValue(true);
    const onSuccess = vi.fn();
    render(<LoginScreen onSuccess={onSuccess} />);

    fireEvent.change(screen.getByTestId("auth-token-input"), { target: { value: "  good-token  " } });
    fireEvent.click(screen.getByTestId("auth-signin"));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    // the candidate is trimmed before validation + storage
    expect(validateToken).toHaveBeenCalledWith("good-token");
    expect(getToken()).toBe("good-token");
    expect(hasStoredToken()).toBe(true);
  });

  it("C(invalid): a rejected token shows the error and is NOT stored", async () => {
    validateToken.mockResolvedValue(false);
    const onSuccess = vi.fn();
    render(<LoginScreen onSuccess={onSuccess} />);

    fireEvent.change(screen.getByTestId("auth-token-input"), { target: { value: "bad-token" } });
    fireEvent.click(screen.getByTestId("auth-signin"));

    expect(await screen.findByText(/rejected/i)).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(hasStoredToken()).toBe(false);
  });

  it("C(gate-after-valid): AuthGate re-renders its children after a successful sign-in", async () => {
    validateToken.mockResolvedValue(true);
    render(
      <AuthGate>
        <div data-testid="the-app">the product</div>
      </AuthGate>,
    );
    act(() => {
      window.dispatchEvent(new Event(AUTH_EVENT));
    });
    await screen.findByTestId("auth-token-input");

    fireEvent.change(screen.getByTestId("auth-token-input"), { target: { value: "good" } });
    fireEvent.click(screen.getByTestId("auth-signin"));

    // children return (the app re-mounts to re-fetch with the new token)
    expect(await screen.findByTestId("the-app")).toBeInTheDocument();
    expect(screen.queryByTestId("auth-token-input")).toBeNull();
  });
});

describe("token helpers — UI-LOGIN-1 (D): the localStorage round-trip + the env fallback", () => {
  it("D: setToken/getToken/hasStoredToken/clearToken round-trip via localStorage", () => {
    expect(hasStoredToken()).toBe(false);
    setToken("abc123");
    expect(getToken()).toBe("abc123");
    expect(hasStoredToken()).toBe(true);
    clearToken();
    expect(hasStoredToken()).toBe(false);
  });

  it("D: getToken falls back to VITE_BFF_TOKEN when nothing is stored", () => {
    // a build-baked token still works when no runtime token is present
    vi.stubEnv("VITE_BFF_TOKEN", "baked-token");
    clearToken();
    expect(hasStoredToken()).toBe(false);
    expect(getToken()).toBe("baked-token");
    // a stored runtime token takes precedence over the build-baked fallback
    setToken("runtime-token");
    expect(getToken()).toBe("runtime-token");
    vi.unstubAllEnvs();
  });
});

describe("logout — UI-LOGIN-1 (E): clears the token + raises the auth-required signal", () => {
  it("E: logout() clears the stored token AND dispatches lithrim:auth-required", () => {
    setToken("to-be-cleared");
    expect(hasStoredToken()).toBe(true);
    const spy = vi.fn();
    window.addEventListener(AUTH_EVENT, spy);
    logout();
    window.removeEventListener(AUTH_EVENT, spy);
    expect(hasStoredToken()).toBe(false);
    expect(spy).toHaveBeenCalled();
  });
});
