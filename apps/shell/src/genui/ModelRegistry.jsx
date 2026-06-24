/* ModelRegistry.jsx — MODEL-REGISTRY-1c: the model-pool surface inside Connect AI.

   Pick-from-pool, not re-type (SPEC_COMMUNITY_EDITION §8): register a capability-annotated
   model ONCE into a reusable pool, then bind each of the 3 fixed judge roles to a pool entry
   instead of re-typing provider/model/key per role.

   Capabilities are the UX point — esp. `logprobs`: a model with logprobs:false surfaces a
   ⚠ "no logprobs — confidence dark" hint AT PICK TIME (the differentiated catalog vs a
   cosmetic dropdown). The catalog comes from getModelCatalog (presets {model, logprobs,
   context_window, cost_tier} + the Azure {models, note}); an unknown model is never blocked
   — a "custom" free-text option is always available (Azure is deployment-name free-text by
   design). The key rides a masked password input, is test-probed write-only at register, and
   is NEVER echoed/returned/listed. Conversational-first holds: this is PASSIVE rail chrome —
   it never operates panes / the top-bar to advance the product. Inline styles on the shell
   CSS vars (--bg/--ink/--muted/--border/--accent/--surface-muted/--teal/--amber), reusing the
   ProviderSettings vocabulary. */
import { useEffect, useState } from "react";
import { getModelCatalog, registerModel, listModels, deleteModel, bindModel } from "../bff.js";

const BIND_ROLES = ["risk_judge", "policy_judge", "faithfulness_judge"];
const CUSTOM = "__custom__"; // the always-available free-text sentinel — never block an unknown model

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
const chip = (ok) => ({
  display: "inline-flex", alignItems: "center", gap: 4, fontSize: 10.5, fontWeight: 600,
  padding: "1px 7px", borderRadius: 999,
  color: ok ? "var(--teal)" : "var(--amber)",
  background: ok
    ? "color-mix(in srgb, var(--teal) 14%, transparent)"
    : "color-mix(in srgb, var(--amber) 16%, transparent)",
});

// the catalog presets for a provider (an array for openai/anthropic; azure is {models, note}).
function presetsFor(catalog, provider) {
  const p = catalog?.providers?.[provider];
  if (Array.isArray(p)) return p;
  if (p && Array.isArray(p.models)) return p.models; // azure shape (Phase-1: [] + a note)
  return [];
}
function azureNote(catalog) {
  const a = catalog?.providers?.azure;
  return a && !Array.isArray(a) ? a.note : "";
}
// the chosen model's logprobs flag (preset hit → its flag; custom/unknown → null = unknown).
function logprobsOf(presets, model) {
  const hit = presets.find((m) => m.model === model);
  return hit ? !!hit.logprobs : null;
}

export default function ModelRegistry() {
  const [catalog, setCatalog] = useState({ providers: {} });
  const [pool, setPool] = useState([]);

  // register form
  const [provider, setProvider] = useState("openai");
  const [modelSel, setModelSel] = useState(""); // a preset model id, or CUSTOM
  const [custom, setCustom] = useState("");
  const [id, setId] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [key, setKey] = useState("");
  const [reg, setReg] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  // bind state (per-role selected pool entry id)
  const [bindSel, setBindSel] = useState({});
  const [bindMsg, setBindMsg] = useState({});

  const refreshPool = () => listModels().then((r) => setPool(r?.models || [])).catch(() => {});
  useEffect(() => {
    getModelCatalog({ live: false }).then((c) => setCatalog(c || { providers: {} })).catch(() => {});
    refreshPool();
  }, []);

  const presets = presetsFor(catalog, provider);
  // the effective model id submitted (a preset, or the free-text custom value)
  const effModel = modelSel === CUSTOM ? custom.trim() : modelSel;
  // the picked model's logprobs state, for the ⚠ hint at pick time (null = unknown/custom)
  const pickedLogprobs = modelSel === CUSTOM ? null : logprobsOf(presets, modelSel);

  const onProvider = (p) => { setProvider(p); setModelSel(""); setCustom(""); };

  const submit = async () => {
    setReg({ state: "saving", msg: "testing…" });
    try {
      await registerModel({
        id: id.trim(), provider, model: effModel,
        endpoint: endpoint.trim() || undefined, api_key: key.trim(),
      });
      setReg({ state: "saved", msg: `Registered & tested · ${id.trim()}` });
      setKey(""); // secret hygiene — clear the typed key on success (never re-render it)
      refreshPool();
    } catch (e) {
      setReg({ state: "error", msg: String(e.message || e) });
    }
  };

  const del = async (mid) => {
    try { await deleteModel(mid); refreshPool(); } catch { /* surfaced via the next refresh */ }
  };

  const bind = async (role) => {
    const mid = bindSel[role];
    if (!mid) return;
    setBindMsg((m) => ({ ...m, [role]: "binding…" }));
    try {
      await bindModel(mid, role);
      setBindMsg((m) => ({ ...m, [role]: `bound → ${mid}` }));
      refreshPool();
    } catch (e) {
      setBindMsg((m) => ({ ...m, [role]: String(e.message || e) }));
    }
  };

  const regColor = reg.state === "error" ? "var(--amber)" : "var(--teal)";
  const canRegister = !!id.trim() && !!effModel && !!key.trim() &&
    (provider !== "azure" || !!endpoint.trim());

  return (
    <section data-testid="model-registry-section"
      style={{ display: "flex", flexDirection: "column", gap: 12, padding: 12, border: "1px solid var(--border)", borderRadius: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>Model pool</div>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>register once · pick-from-pool per role · capability-aware (logprobs)</span>
      </div>

      {/* ── Register a model ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 7, padding: 9, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface-muted)" }}>
        <span style={labelStyle}>Register a model</span>
        <div style={{ display: "flex", gap: 6 }}>
          <select value={provider} onChange={(e) => onProvider(e.target.value)} aria-label="provider"
            data-testid="model-register-provider" style={{ ...inputStyle, width: 120 }}>
            <option value="openai">openai</option>
            <option value="azure">azure</option>
            <option value="anthropic">anthropic</option>
          </select>
          <select value={modelSel} onChange={(e) => setModelSel(e.target.value)} aria-label="model"
            data-testid="model-register-model" style={inputStyle}>
            <option value="">{presets.length ? "— pick a model —" : "— no presets · use custom —"}</option>
            {presets.map((m) => (
              <option key={m.model} value={m.model}>
                {m.model}{m.logprobs === false ? "  ⚠ no logprobs — confidence dark" : ""}
              </option>
            ))}
            <option value={CUSTOM}>custom… (free-text — any model / Azure deployment)</option>
          </select>
        </div>
        {modelSel === CUSTOM && (
          <input value={custom} onChange={(e) => setCustom(e.target.value)} aria-label="custom model"
            data-testid="model-register-custom" placeholder="model id / Azure deployment name" style={inputStyle} />
        )}
        {/* the ⚠ logprobs hint AT PICK TIME — the differentiated-catalog point */}
        {pickedLogprobs === false && (
          <div data-testid="model-logprobs-hint" style={{ fontSize: 11, color: "var(--amber)" }}>
            ⚠ no logprobs — confidence will be dark for this model (no calibrated per-token confidence)
          </div>
        )}
        {modelSel === CUSTOM && (
          <div data-testid="model-logprobs-hint-custom" style={{ fontSize: 11, color: "var(--muted)" }}>
            custom model — capabilities (incl. logprobs) are inferred server-side at register
          </div>
        )}
        {provider === "azure" && (
          <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} aria-label="endpoint"
            data-testid="model-register-endpoint" placeholder="https://…azure endpoint (api_base)" style={inputStyle} />
        )}
        <div style={{ display: "flex", gap: 6 }}>
          <input value={id} onChange={(e) => setId(e.target.value)} aria-label="model pool id"
            data-testid="model-register-id" placeholder="pool id (e.g. grader-gpt4o)" style={{ ...inputStyle, width: 200 }} />
          <input data-testid="model-register-key" type="password" autoComplete="off" value={key}
            onChange={(e) => setKey(e.target.value)} placeholder="API key (write-only, masked)" style={inputStyle} />
        </div>
        <div>
          <button data-testid="model-register-submit" onClick={submit}
            disabled={reg.state === "saving" || !canRegister} style={btn(true)}>
            {reg.state === "saving" ? "Testing…" : "Register & test"}
          </button>
        </div>
        {azureNote(catalog) && provider === "azure" && (
          <div style={{ fontSize: 10.5, color: "var(--muted)" }}>{azureNote(catalog)}</div>
        )}
        {reg.state !== "idle" && reg.state !== "saving" && (
          <div style={{ fontSize: 11.5, color: regColor }}>{reg.msg}</div>
        )}
      </div>

      {/* ── The pool ── */}
      <div data-testid="model-pool" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={labelStyle}>The pool</span>
        {pool.length === 0 ? (
          <div style={{ fontSize: 11.5, color: "var(--muted)" }}>No models yet — register one above.</div>
        ) : (
          pool.map((m) => {
            const lp = !!m.capabilities?.logprobs;
            return (
              <div key={m.id} data-testid={`model-pool-row-${m.id}`}
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 9px", border: "1px solid var(--border)", borderRadius: 8, background: "var(--bg)" }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--mono)" }}>{m.id}</span>
                <span style={{ fontSize: 11, color: "var(--muted)" }}>{m.provider} · {m.model}</span>
                <span data-testid={`model-pool-logprobs-${m.id}`} style={chip(lp)}>
                  {lp ? "logprobs ✓" : "⚠ no logprobs"}
                </span>
                {(m.bound_roles || []).length > 0 && (
                  <span style={{ fontSize: 10.5, color: "var(--muted)" }}>bound: {m.bound_roles.join(", ")}</span>
                )}
                <button data-testid={`model-pool-delete-${m.id}`} onClick={() => del(m.id)} aria-label={`delete ${m.id}`}
                  style={{ ...btn(false), marginLeft: "auto", padding: "3px 9px", fontSize: 11 }}>Delete</button>
              </div>
            );
          })
        )}
      </div>

      {/* ── Bind roles (pick-from-pool) ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={labelStyle}>Bind the 3 judge roles to pool entries (pick, don't re-type)</span>
        {BIND_ROLES.map((role) => (
          <div key={role} data-testid={`model-bind-row-${role}`}
            style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--mono)", width: 150 }}>{role}</span>
            <select value={bindSel[role] || ""} onChange={(e) => setBindSel((s) => ({ ...s, [role]: e.target.value }))}
              aria-label={`${role} model`} data-testid={`model-bind-select-${role}`} style={inputStyle}>
              <option value="">— pick a pool entry —</option>
              {pool.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id} ({m.provider} · {m.model}{m.capabilities?.logprobs ? "" : " · ⚠ no logprobs"})
                </option>
              ))}
            </select>
            <button data-testid={`model-bind-submit-${role}`} onClick={() => bind(role)}
              disabled={!bindSel[role]} style={{ ...btn(true), whiteSpace: "nowrap" }}>Bind</button>
            {bindMsg[role] && <span style={{ fontSize: 11, color: "var(--muted)" }}>{bindMsg[role]}</span>}
          </div>
        ))}
        <div style={{ fontSize: 10.5, color: "var(--muted)", lineHeight: 1.5 }}>
          Phase-1 binds the same-provider trio; a per-role cross-provider mix is a backend seam (not faked here).
        </div>
      </div>
    </section>
  );
}
