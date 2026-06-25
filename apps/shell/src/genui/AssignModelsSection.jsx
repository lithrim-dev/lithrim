/* AssignModelsSection.jsx — CONNECT-AI-CONSOLIDATE-1, Section 2: one model per consumer.

   FOUR rows — risk_judge, policy_judge, faithfulness_judge, and a now-COMPULSORY chat_assistant
   (CONV-RUNTIME-1 made the chat runtime provider-agnostic, so chat is CROSS-PROVIDER now). Each row
   is a {provider · model} picker sourced from the connected providers + their catalog
   (getModelCatalog), → bindRole(role, provider, model) which REUSES the provider's stored key (no
   re-keying). The ✓ assigned state reads from getRoleBindings; a no-logprobs model surfaces the ⚠
   hint at pick time. A "use one model for all judges" shortcut binds the 3 judge rows in one pick.
   A setup-complete status requires all 3 judges AND chat_assistant (the compulsory-chat gate).
   PASSIVE rail chrome — never operates panes / the top-bar. Inline styles on the shell CSS vars. */
import { useEffect, useState } from "react";
import { getModelCatalog, bindRole } from "../bff.js";
import { NO_LOGPROBS } from "./ProvidersSection.jsx";

const JUDGE_ROLES = ["risk_judge", "policy_judge", "faithfulness_judge"];
const ALL_ROLES = [...JUDGE_ROLES, "chat_assistant"];
const ROLE_LABEL = {
  risk_judge: "risk_judge", policy_judge: "policy_judge",
  faithfulness_judge: "faithfulness_judge", chat_assistant: "chat_assistant",
};
const SEP = "::"; // the picker value encodes provider::model

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

// the connected providers' {provider, model} options drawn from the catalog presets.
function optionsFor(catalog, connected) {
  const out = [];
  for (const p of connected) {
    for (const m of presetsFor(catalog, p)) {
      out.push({ value: `${p}${SEP}${m.model}`, provider: p, model: m.model, logprobs: !!m.logprobs });
    }
  }
  return out;
}

export default function AssignModelsSection({ connected = [], bindings = {}, onBound }) {
  const [catalog, setCatalog] = useState({ providers: {} });
  const [sel, setSel] = useState({}); // per-role picked "provider::model"
  const [allJudges, setAllJudges] = useState(""); // the shortcut pick
  const [msg, setMsg] = useState({});

  useEffect(() => {
    getModelCatalog({ live: false }).then((c) => setCatalog(c || { providers: {} })).catch(() => {});
  }, []);

  const options = optionsFor(catalog, connected);
  const parse = (v) => { const i = v.indexOf(SEP); return i < 0 ? null : { provider: v.slice(0, i), model: v.slice(i + SEP.length) }; };

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

  const bindRow = (role) => {
    const pm = parse(sel[role] || "");
    if (pm) doBind(role, pm.provider, pm.model);
  };

  const bindAllJudges = () => {
    const pm = parse(allJudges);
    if (!pm) return;
    for (const role of JUDGE_ROLES) doBind(role, pm.provider, pm.model);
  };

  // the compulsory-chat gate: all 3 judges AND chat_assistant bound.
  const isBound = (role) => !!bindings?.[role]?.provider;
  const judgesBound = JUDGE_ROLES.filter(isBound).length;
  const chatBound = isBound("chat_assistant");
  const boundCount = judgesBound + (chatBound ? 1 : 0);
  const ready = judgesBound === 3 && chatBound;

  return (
    <section data-testid="assign-models-section"
      style={{ display: "flex", flexDirection: "column", gap: 12, padding: 12, border: "1px solid var(--border)", borderRadius: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>2 · Assign models</div>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>one model per consumer · reuses the stored key (no re-keying)</span>
      </div>

      {/* ── use one model for all judges shortcut ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600, width: 150 }}>use one model for all judges</span>
        <select value={allJudges} onChange={(e) => setAllJudges(e.target.value)} aria-label="all judges model"
          data-testid="all-judges-select" style={inputStyle}>
          <option value="">— pick provider · model —</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>{o.provider} · {o.model}{o.logprobs ? "" : " · ⚠ no logprobs"}</option>
          ))}
        </select>
        <button data-testid="all-judges-submit" onClick={bindAllJudges} disabled={!allJudges}
          style={{ ...btn(false), whiteSpace: "nowrap" }}>Apply to 3 judges</button>
      </div>

      {/* ── the four consumer rows ── */}
      {ALL_ROLES.map((role) => {
        const pm = parse(sel[role] || "");
        const pickedLogprobs = pm ? modelLogprobs(catalog, pm.provider, pm.model) : true;
        const bound = bindings?.[role];
        const isChat = role === "chat_assistant";
        return (
          <div key={role} data-testid={`role-bind-row-${role}`}
            style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--mono)", width: 150 }}>
                {ROLE_LABEL[role]}
                {isChat && <span style={{ marginLeft: 6, fontSize: 9.5, fontWeight: 700, color: "var(--accent)", textTransform: "uppercase" }}>required</span>}
              </span>
              <select value={sel[role] || ""} onChange={(e) => setSel((s) => ({ ...s, [role]: e.target.value }))}
                aria-label={`${role} model`} data-testid={`role-bind-select-${role}`} style={inputStyle}>
                <option value="">— pick provider · model —</option>
                {options.map((o) => (
                  <option key={o.value} value={o.value}>{o.provider} · {o.model}{o.logprobs ? "" : " · ⚠ no logprobs"}</option>
                ))}
              </select>
              <button data-testid={`role-bind-submit-${role}`} onClick={() => bindRow(role)}
                disabled={!sel[role]} style={{ ...btn(true), whiteSpace: "nowrap" }}>Assign</button>
              {bound?.provider && (
                <span data-testid={`role-bind-assigned-${role}`} style={{ fontSize: 10.5, color: "var(--teal)", whiteSpace: "nowrap" }}>
                  ✓ {bound.provider} · {bound.model}
                </span>
              )}
            </div>
            {pm && !pickedLogprobs && (
              <div data-testid={`role-bind-logprobs-hint-${role}`} style={{ fontSize: 10.5, color: "var(--amber)", paddingLeft: 156 }}>
                ⚠ no logprobs — confidence will be dark for {pm.provider} · {pm.model}
              </div>
            )}
            {msg[role] && <span style={{ fontSize: 10.5, color: "var(--muted)", paddingLeft: 156 }}>{msg[role]}</span>}
          </div>
        );
      })}

      {/* ── the setup-complete (compulsory-chat) gate ── */}
      <div data-testid="setup-complete-status"
        style={{ fontSize: 11.5, fontWeight: 600, color: ready ? "var(--teal)" : "var(--amber)" }}>
        {ready
          ? `Ready — 4 of 4 roles assigned`
          : chatBound
            ? `Not ready — ${boundCount} of 4 roles assigned (a judge still needs a model)`
            : `Chat assistant still needs a model — ${boundCount} of 4 roles assigned`}
      </div>
    </section>
  );
}
