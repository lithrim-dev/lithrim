/* AssignModelsSection.jsx — CONNECT-AI-CONSOLIDATE-1 / CONNECT-AI-AZURE-1: one model per consumer.

   FOUR rows — risk_judge, policy_judge, faithfulness_judge, and a now-COMPULSORY chat_assistant
   (CONV-RUNTIME-1 made the chat runtime provider-agnostic, so chat is CROSS-PROVIDER now). Each row
   is a {provider · model} picker: a provider <select> (connected providers) + a model <input
   list=datalist> that offers that provider's catalog presets AND accepts FREE TEXT — so a
   deployment-based provider (Azure) whose catalog is {models:[]} can have its deployment TYPED, not
   only picked (CONNECT-AI-AZURE-1, the EMPTY-picker fix). → bindRole(role, provider, model) which
   REUSES the provider's stored key (no re-keying). The ✓ assigned state reads from getRoleBindings;
   a no-logprobs model surfaces the ⚠ hint at pick time. A "use one model for all judges" shortcut
   binds the 3 judge rows in one pick. A setup-complete status requires all 3 judges AND
   chat_assistant (the compulsory-chat gate). PASSIVE rail chrome — never operates panes / the
   top-bar. Inline styles on the shell CSS vars. */
import { useEffect, useState } from "react";
import { getModelCatalog, bindRole } from "../bff.js";
import { NO_LOGPROBS } from "./ProvidersSection.jsx";
import { roleLabel } from "./copy.js";

const JUDGE_ROLES = ["risk_judge", "policy_judge", "faithfulness_judge"];
const ALL_ROLES = [...JUDGE_ROLES, "chat_assistant"];

const inputStyle = {
  padding: "6px 8px", fontSize: 12.5, borderRadius: 6, border: "1px solid var(--border)",
  background: "var(--bg)", color: "var(--ink)", width: "100%", boxSizing: "border-box",
};
const labelStyle = { fontSize: 11, color: "var(--muted)", fontWeight: 600 };
const btn = (primary) => ({
  padding: "6px 12px", fontSize: 12, borderRadius: 6, border: "none", cursor: "pointer",
  background: primary ? "var(--accent)" : "var(--surface-muted)",
  color: primary ? "#fff" : "var(--ink)", fontWeight: 600,
});
// CONNECT-AI-LAYOUT-1: every consumer row shares ONE column grid so label · provider · model · action
// align across rows; minmax(_,1fr) lets the model input flex (never the variable status label starving
// it). The assigned `✓ provider · model` status is lifted to its OWN line (STATUS_INDENT) so a long
// model id wraps there instead of crushing the controls / forcing the modal to scroll horizontally.
const ROW_GRID = {
  display: "grid", gridTemplateColumns: "150px 128px minmax(120px, 1fr) auto",
  alignItems: "center", gap: 8,
};
const STATUS_INDENT = 158; // align status / hints under the controls (150 label + 8 gap)

// the catalog presets for a provider (an array for openai/anthropic/gemini; azure is {models, note}).
function presetsFor(catalog, provider) {
  const p = catalog?.providers?.[provider];
  if (Array.isArray(p)) return p;
  if (p && Array.isArray(p.models)) return p.models; // azure shape ([] + a note)
  return [];
}
// the model logprobs flag (preset hit → its flag; else fall back to the provider default).
function modelLogprobs(catalog, provider, model) {
  const hit = presetsFor(catalog, provider).find((m) => m.model === model);
  if (hit) return !!hit.logprobs;
  return !NO_LOGPROBS.has(provider);
}

export default function AssignModelsSection({ connected = [], bindings = {}, onBound }) {
  const [catalog, setCatalog] = useState({ providers: {} });
  // per-role picked {provider, model} (free-text model). The "all judges" shortcut is keyed under "*".
  const [sel, setSel] = useState({});
  const [msg, setMsg] = useState({});

  useEffect(() => {
    getModelCatalog({ live: false }).then((c) => setCatalog(c || { providers: {} })).catch(() => {});
  }, []);

  // CONNECT-AI-PREFILL-1: seed each row's picker from its SAVED binding so an already-configured role
  // shows its provider+model in the editable controls (not an empty field next to a ✓). Only seed a row
  // the user hasn't touched (absent from `sel`) — never clobber an in-progress edit; no-op once seeded.
  useEffect(() => {
    setSel((s) => {
      let changed = false;
      const next = { ...s };
      for (const role of ALL_ROLES) {
        const b = bindings?.[role];
        if (b?.provider && next[role] === undefined) {
          next[role] = { provider: b.provider, model: b.model || "" };
          changed = true;
        }
      }
      return changed ? next : s;
    });
  }, [bindings]);

  const pick = (key) => sel[key] || { provider: "", model: "" };
  const setProvider = (key, provider) =>
    setSel((s) => ({ ...s, [key]: { provider, model: pick(key).model } }));
  const setModel = (key, model) =>
    setSel((s) => ({ ...s, [key]: { provider: pick(key).provider, model } }));

  const doBind = async (role, provider, model) => {
    setMsg((m) => ({ ...m, [role]: "binding…" }));
    try {
      await bindRole({ role, provider, model });
      setMsg((m) => ({ ...m, [role]: `bound → ${provider} · ${model}` }));
      onBound?.();
    } catch (e) {
      setMsg((m) => ({ ...m, [role]: String(e.message || e) }));
    }
  };

  const canBind = (key) => { const p = pick(key); return !!p.provider && !!p.model.trim(); };
  const bindRow = (role) => { const p = pick(role); if (canBind(role)) doBind(role, p.provider, p.model.trim()); };
  const bindAllJudges = () => {
    const p = pick("*");
    if (!canBind("*")) return;
    for (const role of JUDGE_ROLES) doBind(role, p.provider, p.model.trim());
  };

  // the compulsory-chat gate: all 3 judges AND chat_assistant bound.
  const isBound = (role) => !!bindings?.[role]?.provider;
  const judgesBound = JUDGE_ROLES.filter(isBound).length;
  const chatBound = isBound("chat_assistant");
  const boundCount = judgesBound + (chatBound ? 1 : 0);
  const ready = judgesBound === 3 && chatBound;

  // one provider <select> + a model <input list=datalist> (presets + free text). `key` namespaces
  // the row (a role or "*" for the all-judges shortcut); `idPrefix` is the datalist + testid stem.
  const pickerControls = (key, idPrefix) => {
    const p = pick(key);
    const presets = presetsFor(catalog, p.provider);
    const listId = `${idPrefix}-modellist-${key}`;
    return (
      <>
        <select value={p.provider} onChange={(e) => setProvider(key, e.target.value)}
          aria-label={`${key} provider`} data-testid={`${idPrefix}-provider-${key}`}
          style={inputStyle}>
          <option value="">— provider —</option>
          {connected.map((cp) => (<option key={cp} value={cp}>{cp}</option>))}
        </select>
        <input value={p.model} onChange={(e) => setModel(key, e.target.value)}
          aria-label={`${key} model`} data-testid={`${idPrefix}-model-${key}`}
          list={listId} placeholder="model name" autoComplete="off" style={inputStyle} />
        <datalist id={listId} data-testid={`${idPrefix}-modellist-${key}`}>
          {presets.map((m) => (
            <option key={m.model} value={m.model}>{m.logprobs ? "" : "⚠ no logprobs"}</option>
          ))}
        </datalist>
      </>
    );
  };

  return (
    <section data-testid="assign-models-section"
      style={{ display: "flex", flexDirection: "column", gap: 12, padding: 12, border: "1px solid var(--border)", borderRadius: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>2 · Assign models</div>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>one model per reviewer · type your Azure model name · uses your saved key</span>
      </div>

      {/* ── use one model for all judges shortcut ── */}
      <div style={ROW_GRID}>
        <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600 }}>use one model for all reviewers</span>
        {pickerControls("*", "all-judges")}
        <button data-testid="all-judges-submit" onClick={bindAllJudges} disabled={!canBind("*")}
          style={{ ...btn(false), whiteSpace: "nowrap" }}>Apply to 3 reviewers</button>
      </div>

      {/* ── the four consumer rows ── */}
      {ALL_ROLES.map((role) => {
        const p = pick(role);
        const pickedLogprobs = p.provider && p.model ? modelLogprobs(catalog, p.provider, p.model) : true;
        const bound = bindings?.[role];
        const isChat = role === "chat_assistant";
        return (
          <div key={role} data-testid={`role-bind-row-${role}`}
            style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={ROW_GRID}>
              <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--mono)" }}>
                {roleLabel(role)}
                {isChat && <span style={{ marginLeft: 6, fontSize: 9.5, fontWeight: 700, color: "var(--accent)", textTransform: "uppercase" }}>required</span>}
              </span>
              {pickerControls(role, "role-bind")}
              <button data-testid={`role-bind-submit-${role}`} onClick={() => bindRow(role)}
                disabled={!canBind(role)} style={{ ...btn(true), whiteSpace: "nowrap" }}>Assign</button>
            </div>
            {bound?.provider && (
              <span data-testid={`role-bind-assigned-${role}`}
                style={{ fontSize: 10.5, color: "var(--teal)", paddingLeft: STATUS_INDENT, wordBreak: "break-word" }}>
                ✓ {bound.provider} · {bound.model}
              </span>
            )}
            {p.provider && p.model && !pickedLogprobs && (
              <div data-testid={`role-bind-logprobs-hint-${role}`} style={{ fontSize: 10.5, color: "var(--amber)", paddingLeft: STATUS_INDENT }}>
                ⚠ this model doesn't report a confidence signal — "{p.provider} · {p.model}" won't show a confidence number
              </div>
            )}
            {msg[role] && <span style={{ fontSize: 10.5, color: "var(--muted)", paddingLeft: STATUS_INDENT }}>{msg[role]}</span>}
          </div>
        );
      })}

      {/* ── the setup-complete (compulsory-chat) gate ── */}
      <div data-testid="setup-complete-status"
        style={{ fontSize: 11.5, fontWeight: 600, color: ready ? "var(--teal)" : "var(--amber)" }}>
        {ready
          ? `Ready — all 4 set`
          : chatBound
            ? `Not ready — ${boundCount} of 4 set (a reviewer still needs a model)`
            : `The assistant needs a model before you can chat — ${boundCount} of 4 set`}
      </div>
    </section>
  );
}
