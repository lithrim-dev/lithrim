/* CostModal.jsx — the in-DOM PAID-run cost confirm (UAP-5b D5 / S-BS-69).

   The A-SAFE boundary made visible: the conversational agent can NEVER fire a paid
   run (its run_eval tool is replay-only, $0). A live / in-process run is the HUMAN's
   explicit, cost-confirmed action — gated by THIS in-DOM modal, never window.confirm
   (a native confirm() freezes the renderer to Claude-in-Chrome/CDP and can't be
   driven in a browser smoke; memory browser-mcp-confirm-blocks-renderer). On confirm
   the caller hits the existing confirm-gated BFF endpoint. Inline-styled + brand
   tokens (no CSS file edits), matching ModeSwitch.

   A11Y: labelled by its own title (aria-labelledby), Escape cancels (a discoverable keyboard
   exit, not only a backdrop click), and focus moves to the confirm button on open so a keyboard
   user lands inside the dialog. */
import { useEffect, useRef } from "react";

export function CostModal({ open, title, body, confirmLabel = "Run (paid)", onConfirm, onCancel, busy, warning }) {
  const confirmRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape" && !busy) onCancel?.(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cost-modal-title"
      onClick={onCancel}
      style={{
        position: "fixed", inset: 0, zIndex: 50, display: "flex",
        alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.38)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 420, maxWidth: "90vw", background: "var(--surface, #fff)",
          border: "1px solid var(--border)", borderRadius: 12, padding: 20,
          boxShadow: "0 12px 40px rgba(0,0,0,0.28)", color: "var(--text, #111)",
        }}
      >
        <div id="cost-modal-title" style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>{title}</div>
        <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--muted, #555)", marginBottom: warning ? 10 : 16 }}>
          {body}
        </div>
        {warning && (
          <div data-testid="cost-readiness-warning" style={{ fontSize: 12.5, lineHeight: 1.45, color: "var(--amber, #b8860b)", background: "var(--amber-bg, rgba(210,150,20,0.08))", borderLeft: "3px solid var(--amber, #b8860b)", borderRadius: 6, padding: "8px 10px", marginBottom: 16 }}>
            {warning}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
          <button ref={confirmRef} className="btn btn-primary" data-testid="cost-confirm" onClick={onConfirm} disabled={busy}>
            {busy ? "Running…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
