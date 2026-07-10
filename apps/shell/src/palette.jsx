/* palette.jsx — CMDK-1: the ⌘K command palette (UI-pass 2026-07-04 P1 #6).

   The top-bar "Search or run a command… ⌘K" and the rail "Search ⌘K" were inert static divs —
   dead chrome advertising a shortcut that did nothing (the no-static-components rule). This is
   the real thing behind both: one fuzzy-filtered list over the core ACTIONS, the workspace's
   other EVALUATIONS (switch), and the browsable CASES (the CASE-BROWSER-1 read — the same rows
   the Cases tab shows, so "press ⌘K, type the case name" works in a guide). Keyboard-first:
   ↑/↓ select, Enter runs, Esc closes; clicking the dimmed backdrop closes.

   A-SAFE: an action is a CALLBACK the App owns — the paid "Run live" entry routes through
   requestRun(true) → the S-BS-80 in-DOM cost-confirm. The palette itself never spends. */
import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./icons.jsx";
import { listCaseBrowser } from "./bff.js";
import { flagLabel } from "./genui/copy.js";

const _CASE_ROWS_MAX = 40; // the list stays keyboard-scannable; typing narrows further

export function CommandPalette({
  open, onClose, actions = [], agents = [], activeAgent = null, onSwitchAgent, onSelectCase,
  agent = "ws0_default",
}) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [cases, setCases] = useState([]);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    setQ("");
    setSel(0);
    // focus after paint so the global ⌘K keydown that opened us doesn't land in the input
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    let live = true;
    listCaseBrowser(agent)
      .then((b) => { if (live) setCases((b || {}).cases || []); })
      .catch(() => {}); // offline-safe: actions still work, never a crash
    return () => { live = false; clearTimeout(t); };
  }, [open, agent]);

  const items = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const hit = (s) => !needle || String(s).toLowerCase().includes(needle);
    const out = [];
    for (const a of actions) if (hit(a.label)) out.push({ kind: "action", id: a.id, label: a.label, hint: a.hint, run: a.run });
    for (const name of agents) {
      if (name === activeAgent || !hit(name)) continue;
      out.push({ kind: "evaluation", id: name, label: name, hint: "switch to this evaluation", run: () => onSwitchAgent?.(name) });
    }
    let shown = 0;
    for (const c of cases) {
      if (shown >= _CASE_ROWS_MAX) break;
      if (!hit(c.case_id)) continue;
      shown += 1;
      out.push({
        kind: "case", id: c.case_id, label: c.case_id,
        hint: c.labeled ? (c.defect ? flagLabel(c.defect) : "clean") : "unlabeled",
        run: () => onSelectCase?.(c.case_id),
      });
    }
    return out;
  }, [q, actions, agents, activeAgent, cases, onSwitchAgent, onSelectCase]);

  useEffect(() => { setSel((s) => Math.min(s, Math.max(items.length - 1, 0))); }, [items.length]);

  if (!open) return null;
  const runItem = (it) => { onClose?.(); it.run?.(); };
  const onKey = (e) => {
    if (e.key === "Escape") { e.preventDefault(); onClose?.(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter" && items[sel]) { e.preventDefault(); runItem(items[sel]); }
  };
  return (
    <div className="cmdk-overlay" data-testid="cmdk"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="cmdk" role="dialog" aria-label="Command palette">
        <div className="cmdk-input">
          <Icon name="search" size={15} />
          <input ref={inputRef} data-testid="cmdk-input" placeholder="Search cases, evaluations, commands…"
            value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }} onKeyDown={onKey} />
          <span className="kbd">esc</span>
        </div>
        <div className="cmdk-list">
          {items.length === 0 && <div className="cmdk-empty">No matches.</div>}
          {items.map((it, i) => (
            <div key={`${it.kind}:${it.id}`} data-testid={`cmdk-item-${it.id}`}
              className={"cmdk-item" + (i === sel ? " on" : "")}
              onMouseEnter={() => setSel(i)} onClick={() => runItem(it)}>
              <span className="cmdk-kind">{it.kind}</span>
              <span className="cmdk-label">{it.label}</span>
              {it.hint && <span className="cmdk-hint">{it.hint}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
