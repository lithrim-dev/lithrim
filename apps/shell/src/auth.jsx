/* auth.jsx — UI-LOGIN-1: the runtime BFF login gate.

   A REACTIVE pre-auth screen: it replaces the app ONLY when a 401 raises the `window`
   "lithrim:auth-required" signal (bff.js call()/logout()). With the server gate off (the local
   default) no 401 ever fires, so the gate never shows — the one-command run is unchanged. The
   token is a CLIENT credential entered here, validated against a gated route, and stored in
   localStorage (NOT baked into the bundle). Conversational-first holds: this is a pre-auth
   screen + rail chrome (the logout button), never chrome operating the product. */
import { useState, useEffect } from "react";
import { Mark } from "./brand.jsx";
import { setToken, validateToken } from "./bff.js";
import { friendlyError } from "./genui/copy.js";

export function LoginScreen({ onSuccess, onCancel }) {
  const [token, setTok] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e) {
    e?.preventDefault?.();
    const t = token.trim();
    if (!t || busy) return;
    setBusy(true); setErr("");
    const ok = await validateToken(t);
    if (ok) { setToken(t); onSuccess?.(); return; }
    setBusy(false);
    setErr("That token was rejected — check it and try again.");
  }

  return (
    <div style={{ position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg)", zIndex: 1000 }}>
      <form onSubmit={submit} style={{ width: 360, maxWidth: "90vw", padding: 28, borderRadius: 14, background: "var(--panel)", border: "1px solid var(--border)", boxShadow: "0 8px 40px rgba(0,0,0,0.18)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          <span style={{ display: "inline-flex", width: 34, height: 34, alignItems: "center", justifyContent: "center", borderRadius: 9, background: "var(--ink)" }}><Mark size={20} /></span>
          <div style={{ fontWeight: 700, letterSpacing: "0.06em", color: "var(--text)" }}>LITHRIM</div>
        </div>
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>This workspace is protected. Enter the access token to continue.</div>
        <input
          data-testid="auth-token-input"
          type="password"
          autoFocus
          value={token}
          onChange={(e) => setTok(e.target.value)}
          placeholder="Access token"
          style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", borderRadius: 9, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 14, outline: "none" }}
        />
        {err && <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--accent)" }}>{friendlyError(err)}</div>}
        <button
          data-testid="auth-signin"
          type="submit"
          disabled={busy || !token.trim()}
          style={{ marginTop: 16, width: "100%", padding: "10px 12px", borderRadius: 9, border: "none", background: "var(--accent)", color: "#fff", fontWeight: 600, fontSize: 14, cursor: busy || !token.trim() ? "default" : "pointer", opacity: busy || !token.trim() ? 0.55 : 1 }}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {/* SESSION-MENU-1: a PROACTIVE sign-in (esp. on an open server, where any token validates)
            must not be a dead-end — a subtle escape returns to the app. On a genuine 401 the next
            call simply re-raises the gate. */}
        {onCancel && (
          <button
            data-testid="auth-cancel"
            type="button"
            onClick={onCancel}
            style={{ marginTop: 12, width: "100%", padding: "6px 12px", borderRadius: 9, border: "none", background: "transparent", color: "var(--muted)", fontSize: 12.5, cursor: "pointer" }}
          >
            Continue without signing in
          </button>
        )}
      </form>
    </div>
  );
}

export function AuthGate({ children }) {
  const [needsLogin, setNeedsLogin] = useState(false);
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    const onRequired = () => setNeedsLogin(true);
    window.addEventListener("lithrim:auth-required", onRequired);
    return () => window.removeEventListener("lithrim:auth-required", onRequired);
  }, []);

  return needsLogin ? (
    <LoginScreen
      onSuccess={() => { setNeedsLogin(false); setEpoch((e) => e + 1); }}
      onCancel={() => setNeedsLogin(false)}
    />
  ) : (
    // bumping `epoch` REMOUNTS the children so the app re-fetches with the new token — no reload.
    <div key={epoch} style={{ display: "contents" }}>{children}</div>
  );
}
