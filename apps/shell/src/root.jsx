/* root.jsx — the Shell↔Journey mode switch. Holds `mode` and owns the shared `theme` so
   toggling modes preserves it (the eval shell and the activation journey each receive
   theme/setTheme + mode/setMode as props). The switch itself (components/ModeSwitch.jsx)
   is rendered inside each shell's titlebar chrome (WS-5c).

   Default = "shell": the real conversational product is the entry (audit 2026-06-07 — a
   fresh user must land in the product, not the frozen demo). The Journey demo is gated
   behind it: reachable via the titlebar ModeSwitch, or deep-linked for sales/investor
   runs with `?demo` (or `?mode=journey`); `?mode=shell` forces the product. Real
   first-run activation gating remains product logic for a later phase. */
import { useState, useEffect } from "react";
import App from "./app.jsx";
import { JourneyApp } from "./journey/JourneyApp.jsx";
import { AuthGate } from "./auth.jsx"; // UI-LOGIN-1: the reactive runtime BFF login gate

// Entry mode: the product by default; honor an explicit query param so the demo stays
// bookmarkable without making it the default surface.
function initialMode() {
  try {
    const q = new URLSearchParams(window.location.search);
    const m = q.get("mode");
    if (m === "journey" || m === "shell") return m;
    if (q.has("demo")) return "journey";
  } catch { /* no window (SSR/tests): fall through to the product */ }
  return "shell";
}

export default function RootApp() {
  const [mode, setMode] = useState(initialMode);
  const [theme, setTheme] = useState("light");

  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  const shared = { theme, setTheme, mode, setMode };
  return (
    <AuthGate>
      {mode === "journey" ? <JourneyApp {...shared} /> : <App {...shared} />}
    </AuthGate>
  );
}
