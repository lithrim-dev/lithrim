/* ConsumerBind.jsx — PROVIDER-CENTER-B: the per-CONSUMER picker (the Cline "use different models for X").

   Two honest consumers over the shared model pool (listModels):
     · GRADING — the 3 judge roles, each a {provider, model} pool pick → bindModel(id, role). PROVIDER-
       CENTER-A makes this bind CROSS-PROVIDER (risk→openai + policy→gemini coexist), so each option
       shows the model's provider, and a logprobs:false entry surfaces the ⚠ no-logprobs hint at pick
       time (now also gemini/bedrock/anthropic → confidence dark).
     · CONVERSATION — an ANTHROPIC-only model pick from the pool, with an honest inline note: the
       assistant runs on the Anthropic Agent SDK, so other providers GRADE but don't yet drive the chat.
       (No fake "any-provider chat" — the picker only lists the anthropic pool entries.)

   PASSIVE rail chrome — never operates panes / the top-bar. Inline styles on the shell CSS vars,
   reusing the ModelRegistry / ProviderSettings vocabulary. */
import { useEffect, useState } from "react";
import { listModels, bindModel } from "../bff.js";

const BIND_ROLES = ["risk_judge", "policy_judge", "faithfulness_judge"];

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

const logprobsOf = (m) => !!m?.capabilities?.logprobs;

export default function ConsumerBind() {
  const [pool, setPool] = useState([]);
  const [bindSel, setBindSel] = useState({}); // per-role selected pool id
  const [bindMsg, setBindMsg] = useState({});

  const refresh = () => listModels().then((r) => setPool(r?.models || [])).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const byId = (id) => pool.find((m) => m.id === id);
  // the conversation is Anthropic-only: the assistant runs on the Anthropic Agent SDK.
  const anthropicPool = pool.filter((m) => m.provider === "anthropic");

  const bind = async (role) => {
    const mid = bindSel[role];
    if (!mid) return;
    setBindMsg((m) => ({ ...m, [role]: "binding…" }));
    try {
      await bindModel(mid, role);
      setBindMsg((m) => ({ ...m, [role]: `bound → ${mid}` }));
      refresh();
    } catch (e) {
      setBindMsg((m) => ({ ...m, [role]: String(e.message || e) }));
    }
  };

  return (
    <section data-testid="consumer-bind-section"
      style={{ display: "flex", flexDirection: "column", gap: 12, padding: 12, border: "1px solid var(--border)", borderRadius: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>Use different models for…</div>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>grading (per-judge, any provider) · conversation (Anthropic)</span>
      </div>

      {/* ── Grading: per-judge cross-provider bind ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={labelStyle}>Grading — each judge picks any provider/model from the pool (cross-provider council)</span>
        {BIND_ROLES.map((role) => {
          const picked = byId(bindSel[role]);
          return (
            <div key={role} data-testid={`judge-bind-row-${role}`}
              style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--mono)", width: 150 }}>{role}</span>
                <select value={bindSel[role] || ""} onChange={(e) => setBindSel((s) => ({ ...s, [role]: e.target.value }))}
                  aria-label={`${role} model`} data-testid={`judge-bind-select-${role}`} style={inputStyle}>
                  <option value="">— pick provider · model —</option>
                  {pool.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.id} ({m.provider} · {m.model}{logprobsOf(m) ? "" : " · ⚠ no logprobs"})
                    </option>
                  ))}
                </select>
                <button data-testid={`judge-bind-submit-${role}`} onClick={() => bind(role)}
                  disabled={!bindSel[role]} style={{ ...btn(true), whiteSpace: "nowrap" }}>Bind</button>
                {bindMsg[role] && <span style={{ fontSize: 11, color: "var(--muted)" }}>{bindMsg[role]}</span>}
              </div>
              {picked && !logprobsOf(picked) && (
                <div data-testid={`judge-bind-logprobs-hint-${role}`} style={{ fontSize: 10.5, color: "var(--amber)", paddingLeft: 156 }}>
                  ⚠ no logprobs — confidence will be dark for {picked.provider} · {picked.model}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Conversation: Anthropic-only. READ-ONLY note that defers to the working "Authoring
          assistant" control (which persists the chat model via configProvider plane=assistant).
          Deliberately NOT an actionable picker: there is no endpoint to set the assistant model
          ALONE, so an editable control here would silently discard the choice + shadow the real
          one below — a misleading no-op. Honest > a fake picker (critic S-BS-PCB-2). ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={labelStyle}>Conversation — the chat assistant (Anthropic only)</span>
        <div data-testid="conversation-anthropic-note" style={{ fontSize: 10.5, color: "var(--muted)", lineHeight: 1.5 }}>
          The assistant runs on the Anthropic Agent SDK, so the conversation is Anthropic-only today —
          set its model in the Authoring assistant section below. Other providers grade (per-judge
          above) but don't yet drive the chat.
          {anthropicPool.length ? (
            <span data-testid="conversation-anthropic-models">
              {" "}Configured Anthropic models: {anthropicPool.map((m) => m.model).join(", ")}.
            </span>
          ) : null}
        </div>
      </div>
    </section>
  );
}
