/* root.jsx — the Shell↔Journey mode switch. Holds `mode` (default "journey" for the
   demo) and owns the shared `theme` so toggling modes preserves it (the eval shell and
   the activation journey each receive theme/setTheme + mode/setMode as props). The
   switch itself (components/ModeSwitch.jsx) is now rendered inside each shell's
   titlebar chrome (WS-5c) rather than as a fixed-position floating overlay. It stays a
   thin dev/demo toggle; real first-run activation gating is product logic for a later
   phase. */
import { useState, useEffect } from "react";
import App from "./app.jsx";
import { JourneyApp } from "./journey/JourneyApp.jsx";

export default function RootApp() {
  const [mode, setMode] = useState("journey");
  const [theme, setTheme] = useState("light");

  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  const shared = { theme, setTheme, mode, setMode };
  return mode === "journey" ? <JourneyApp {...shared} /> : <App {...shared} />;
}
