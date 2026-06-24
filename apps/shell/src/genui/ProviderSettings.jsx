/* ProviderSettings.jsx — CE-PROVIDER-UI (Build B): the in-app "Connect AI" surface.

   A capability-oriented provider-connect panel (SPEC_COMMUNITY_EDITION §3.2/§3.3):
     · Grading engine (REQUIRED) — Simple (one OpenAI key → the trio on gpt-4o) | Advanced
       (per-role provider/endpoint/deployment rows for the Azure trio, or any mix).
     · Authoring assistant (OPTIONAL) — an Anthropic key + model, or skip → forms-only authoring.

   Reuses the masked-password + test-then-save idiom of ConnectorForm (app.jsx, read-only ref):
   the secret rides a password input (never echoed), Test & save → configProvider (POST
   /v1/provider/config, which test-probes then write-only persists the key), and a live status
   badge ← getProviderStatus. Conversational-first holds: this is PASSIVE rail chrome — it never
   operates panes / the top-bar to advance the product. Inline styles on the shell CSS vars
   (--bg/--ink/--muted/--border/--accent/--surface-muted/--teal/--amber). */
import { useEffect, useState } from "react";
import { Icon } from "../icons.jsx";
import { configProvider, getProviderStatus } from "../bff.js";
import ModelRegistry from "./ModelRegistry.jsx";
import ProviderPicker from "./ProviderPicker.jsx";
import ConsumerBind from "./ConsumerBind.jsx";

const GRADING_ROLES = ["risk_judge", "policy_judge", "faithfulness_judge"];

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

// the connected / needs-setup badge for a plane, read from getProviderStatus.
function StatusBadge({ testid, plane }) {
  const ok = !!plane?.configured;
  return (
    <span data-testid={testid} style={{
      display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 600,
      padding: "2px 8px", borderRadius: 999, color: ok ? "var(--teal)" : "var(--muted)",
      background: ok ? "color-mix(in srgb, var(--teal) 14%, transparent)" : "var(--surface-muted)",
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: ok ? "var(--teal)" : "var(--muted)" }} />
      {ok ? `Connected${plane.model ? ` · ${plane.model}` : ""}` : "Needs setup"}
    </span>
  );
}

export default function ProviderSettings({ onClose }) {
  const [status, setStatus] = useState({ planes: {} });
  const [advanced, setAdvanced] = useState(false);
  // Simple grading: one OpenAI key.
  const [gKey, setGKey] = useState("");
  // Advanced grading: per-role provider/endpoint/deployment.
  const [roles, setRoles] = useState(() =>
    Object.fromEntries(GRADING_ROLES.map((r) => [r, { provider: "azure", api_key: "", endpoint: "", model: "" }])));
  const [gSave, setGSave] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error
  // Authoring assistant: an Anthropic key + model.
  const [aKey, setAKey] = useState("");
  const [aModel, setAModel] = useState("claude-3-5-sonnet-latest");
  const [aSave, setASave] = useState({ state: "idle", msg: "" });

  const refresh = () => getProviderStatus().then((s) => setStatus(s || { planes: {} })).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const planes = status.planes || {};

  // Simple grading: one OpenAI key → the trio on gpt-4o (no role → all three share the model).
  const saveGradingSimple = async () => {
    setGSave({ state: "saving", msg: "testing…" });
    try {
      const r = await configProvider({ plane: "grading", provider: "openai", api_key: gKey.trim(), model: "gpt-4o" });
      setGSave({ state: "saved", msg: `Connected · tested ${r.last_tested || ""}` });
      setGKey("");
      refresh();
    } catch (e) {
      setGSave({ state: "error", msg: String(e.message || e) });
    }
  };

  // Advanced grading: write one role at a time (per-role provider/endpoint/deployment).
  const saveGradingRole = async (role) => {
    const c = roles[role];
    setGSave({ state: "saving", msg: `testing ${role}…` });
    try {
      const r = await configProvider({
        plane: "grading", provider: c.provider, api_key: c.api_key.trim(),
        endpoint: c.endpoint.trim() || undefined, model: c.model.trim() || undefined, role,
      });
      setGSave({ state: "saved", msg: `${role} connected · tested ${r.last_tested || ""}` });
      setRoles((rs) => ({ ...rs, [role]: { ...rs[role], api_key: "" } }));
      refresh();
    } catch (e) {
      setGSave({ state: "error", msg: String(e.message || e) });
    }
  };

  const saveAssistant = async () => {
    setASave({ state: "saving", msg: "testing…" });
    try {
      const r = await configProvider({ plane: "assistant", provider: "anthropic", api_key: aKey.trim(), model: aModel.trim() || undefined });
      setASave({ state: "saved", msg: `Connected · tested ${r.last_tested || ""}` });
      setAKey("");
      refresh();
    } catch (e) {
      setASave({ state: "error", msg: String(e.message || e) });
    }
  };

  const setRole = (role, patch) => setRoles((rs) => ({ ...rs, [role]: { ...rs[role], ...patch } }));
  const saveColor = (s) => (s.state === "error" ? "var(--amber)" : "var(--teal)");

  return (
    <div data-testid="provider-settings" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="link" size={16} /></span>
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>Connect AI</div>
        <span style={{ fontSize: 11.5, color: "var(--muted)" }}>provider keys are test-probed, then written write-only (never returned)</span>
        {onClose && (
          <button data-testid="provider-settings-close" aria-label="Close" onClick={onClose}
            style={{ marginLeft: "auto", ...btn(false), padding: "4px 8px", display: "inline-flex", alignItems: "center" }}>
            <Icon name="close" size={14} />
          </button>
        )}
      </div>

      {/* ── Provider-FIRST (PROVIDER-CENTER-B): pick a provider, authenticate; its models join the pool ── */}
      <ProviderPicker onSaved={refresh} />

      {/* ── Grading engine (REQUIRED) ── */}
      <section style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, border: "1px solid var(--border)", borderRadius: 10, background: "var(--surface-muted)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "var(--accent)" }}><Icon name="scale" size={14} /></span>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>Grading engine</div>
          <span style={{ fontSize: 10, fontWeight: 700, color: "var(--accent)", textTransform: "uppercase", letterSpacing: 0.5 }}>required</span>
          <span style={{ marginLeft: "auto" }}><StatusBadge testid="grading-status-badge" plane={planes.grading} /></span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button data-testid="grading-simple-toggle" onClick={() => setAdvanced(false)}
            style={{ ...btn(!advanced), padding: "4px 10px", fontSize: 11.5 }} aria-pressed={!advanced}>Simple</button>
          <button data-testid="grading-advanced-toggle" onClick={() => setAdvanced(true)}
            style={{ ...btn(advanced), padding: "4px 10px", fontSize: 11.5 }} aria-pressed={advanced}>Advanced</button>
        </div>

        {!advanced ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            <span style={labelStyle}>OpenAI API key — one key runs all three judges on gpt-4o (calibrated, logprobs on)</span>
            <input data-testid="grading-api-key" type="password" autoComplete="off" value={gKey}
              onChange={(e) => setGKey(e.target.value)} placeholder="sk-… (write-only, masked)" style={inputStyle} />
            <div>
              <button data-testid="grading-test-save" onClick={saveGradingSimple}
                disabled={gSave.state === "saving" || !gKey.trim()} style={btn(true)}>
                {gSave.state === "saving" ? "Testing…" : "Test & save"}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <span style={labelStyle}>Per-role model — provider · endpoint · deployment (the Azure trio, or any mix)</span>
            {GRADING_ROLES.map((role) => {
              const c = roles[role];
              return (
                <div key={role} data-testid={`grading-role-${role}`}
                  style={{ display: "flex", flexDirection: "column", gap: 5, padding: 9, border: "1px solid var(--border)", borderRadius: 8, background: "var(--bg)" }}>
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--mono)" }}>{role}</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <select value={c.provider} onChange={(e) => setRole(role, { provider: e.target.value })}
                      aria-label={`${role} provider`} style={{ ...inputStyle, width: 110 }}>
                      <option value="azure">azure</option>
                      <option value="openai">openai</option>
                    </select>
                    <input value={c.model} onChange={(e) => setRole(role, { model: e.target.value })}
                      placeholder="deployment / model" aria-label={`${role} model`} style={inputStyle} />
                  </div>
                  {c.provider === "azure" && (
                    <input value={c.endpoint} onChange={(e) => setRole(role, { endpoint: e.target.value })}
                      placeholder="https://…azure endpoint (api_base)" aria-label={`${role} endpoint`} style={inputStyle} />
                  )}
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input data-testid={`grading-role-key-${role}`} type="password" autoComplete="off" value={c.api_key}
                      onChange={(e) => setRole(role, { api_key: e.target.value })} placeholder="API key (write-only, masked)" style={inputStyle} />
                    <button data-testid={`grading-role-save-${role}`} onClick={() => saveGradingRole(role)}
                      disabled={gSave.state === "saving" || !c.api_key.trim()} style={{ ...btn(true), whiteSpace: "nowrap" }}>Test &amp; save</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {gSave.state !== "idle" && gSave.state !== "saving" && (
          <div style={{ fontSize: 11.5, color: saveColor(gSave) }}>{gSave.msg}</div>
        )}
      </section>

      {/* ── Model pool (MODEL-REGISTRY-1c): register once, pick-from-pool per role ── */}
      <ModelRegistry />

      {/* ── Per-consumer pickers (PROVIDER-CENTER-B): grading per-judge (any provider) · conversation (Anthropic) ── */}
      <ConsumerBind />

      {/* ── Authoring assistant (OPTIONAL) ── */}
      <section style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, border: "1px solid var(--border)", borderRadius: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "var(--accent)" }}><Icon name="spark" size={14} /></span>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>Authoring assistant</div>
          <span style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>optional</span>
          <span style={{ marginLeft: "auto" }}><StatusBadge testid="assistant-status-badge" plane={planes.assistant} /></span>
        </div>
        <span style={labelStyle}>Anthropic / Claude API key — unlocks chat-authoring. Skip to author with forms instead.</span>
        <div style={{ display: "flex", gap: 6 }}>
          <input data-testid="assistant-api-key" type="password" autoComplete="off" value={aKey}
            onChange={(e) => setAKey(e.target.value)} placeholder="sk-ant-… (write-only, masked)" style={inputStyle} />
          <input value={aModel} onChange={(e) => setAModel(e.target.value)}
            aria-label="assistant model" placeholder="model" style={{ ...inputStyle, width: 190 }} />
        </div>
        <div>
          <button data-testid="assistant-test-save" onClick={saveAssistant}
            disabled={aSave.state === "saving" || !aKey.trim()} style={btn(true)}>
            {aSave.state === "saving" ? "Testing…" : "Test & save"}
          </button>
        </div>
        {aSave.state !== "idle" && aSave.state !== "saving" && (
          <div style={{ fontSize: 11.5, color: saveColor(aSave) }}>{aSave.msg}</div>
        )}
      </section>

      <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.5 }}>
        You can grade now with just the grading engine; chat-author unlocks with an assistant.
      </div>
    </div>
  );
}
