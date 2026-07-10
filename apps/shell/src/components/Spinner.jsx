/* Spinner.jsx — a tiny inline loading spinner. Reuses the .lr-spin keyframe (theme.css) so the
   text-only "Loading…" states (audit, case, reviewer) read as actively loading, not stuck. */
export function Spinner({ size = 12, className = "" }) {
  return (
    <span
      className={"lr-spin " + className}
      aria-hidden
      style={{
        display: "inline-block", width: size, height: size, flex: "0 0 auto",
        border: "2px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%",
      }}
    />
  );
}
