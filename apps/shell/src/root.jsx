/* root.jsx — the Shell↔Journey mode switch. Holds `mode` (default "journey" for the
   demo) and owns the shared `theme` so toggling modes preserves it (the eval shell and
   the activation journey each receive theme/setTheme as props). The switch is a thin,
   self-contained segmented control (inline-styled — no CSS-file edits) floating at the
   top edge, vertically clear of the titlebar's centered command pill. This is a thin
   dev/demo switch; real first-run activation gating is product logic for a later phase. */
import { useState, useEffect } from "react";
import App from "./app.jsx";
import { JourneyApp } from "./journey/JourneyApp.jsx";

const SEG = [
  { id: "journey", label: "Journey" },
  { id: "shell", label: "Shell" },
];

function ModeSwitch({ mode, setMode }) {
  return (
    <div
      role="tablist"
      aria-label="Shell or Journey"
      style={{
        position: "fixed", top: 3, left: "50%", transform: "translateX(-50%)",
        zIndex: 2000, display: "inline-flex", gap: 2, padding: 2,
        background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 999,
        boxShadow: "var(--shadow-win)", fontFamily: "var(--mono)",
      }}
    >
      {SEG.map((s) => {
        const on = mode === s.id;
        return (
          <button
            key={s.id}
            role="tab"
            aria-selected={on}
            onClick={() => setMode(s.id)}
            style={{
              height: 18, padding: "0 10px", border: "none", cursor: "pointer",
              borderRadius: 999, fontSize: 10.5, letterSpacing: "0.04em",
              background: on ? "var(--accent)" : "transparent",
              color: on ? "#fff" : "var(--muted)", fontWeight: on ? 600 : 500,
            }}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}

export default function RootApp() {
  const [mode, setMode] = useState("journey");
  const [theme, setTheme] = useState("light");

  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  return (
    <>
      <ModeSwitch mode={mode} setMode={setMode} />
      {mode === "journey"
        ? <JourneyApp theme={theme} setTheme={setTheme} />
        : <App theme={theme} setTheme={setTheme} />}
    </>
  );
}
