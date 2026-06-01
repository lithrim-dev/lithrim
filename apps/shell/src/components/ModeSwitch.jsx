/* ModeSwitch.jsx — the Shell↔Journey segmented control (WS-5c).

   Promoted out of the WS-5b fixed-position floating overlay (root.jsx) and into the
   titlebar chrome of both shells (app.jsx TopBar + journey chrome.jsx TopBarJ). It
   stays a thin dev/demo toggle — real first-run activation gating is product logic
   for a later phase (plan-review decision 3). Inline-styled + brand tokens (no CSS
   file edits); sized to sit inline among the titlebar buttons. */
const SEG = [
  { id: "journey", label: "Journey" },
  { id: "shell", label: "Shell" },
];

export function ModeSwitch({ mode, setMode }) {
  return (
    <div
      role="tablist"
      aria-label="Shell or Journey"
      style={{
        display: "inline-flex", gap: 2, padding: 2,
        background: "var(--surface-muted)", border: "1px solid var(--border)",
        borderRadius: 999, fontFamily: "var(--mono)", flex: "0 0 auto",
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
              height: 22, padding: "0 11px", border: "none", cursor: "pointer",
              borderRadius: 999, fontSize: 11, letterSpacing: "0.03em",
              background: on ? "var(--accent)" : "transparent",
              color: on ? "#fff" : "var(--muted)", fontWeight: on ? 600 : 500,
              transition: "background .14s, color .14s",
            }}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
