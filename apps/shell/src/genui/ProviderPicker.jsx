/* ProviderPicker.jsx — PROVIDER-CENTER-B: the provider-FIRST auth block (the Cline pattern).

   The lead surface of Connect AI: pick a PROVIDER from the broadened set (openai · anthropic · azure ·
   gemini · bedrock · openai-compatible), supply per-provider auth (a masked key + an endpoint where the
   provider needs one — azure / openai_compatible api_base), then Test & save (REUSES configProvider —
   the same POST /v1/provider/config that test-probes the key read-only, then writes it write-only). The
   secret rides a password input and is CLEARED on success (never echoed/re-rendered). A live status
   badge reads the configured planes. Conversational-first holds: PASSIVE rail chrome — never operates
   panes / the top-bar. Inline styles on the shell CSS vars
   (--bg/--ink/--muted/--border/--accent/--surface-muted/--teal/--amber), reusing the ProviderSettings
   vocabulary. */
import { useState } from "react";
import { configProvider } from "../bff.js";

// the broadened provider set (PROVIDER-CENTER-A). gemini/bedrock/openai_compatible/anthropic grade
// PER-ROLE only — they have no global grading selector — so this picker's global Test & save is the
// connectivity probe; the per-judge picker (below) is what binds a role to one of them.
const PROVIDERS = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Anthropic" },
  { id: "azure", label: "Azure OpenAI" },
  { id: "gemini", label: "Gemini" },
  { id: "bedrock", label: "Bedrock" },
  { id: "openai_compatible", label: "OpenAI-compatible" },
];
// providers whose auth needs an endpoint (api_base): Azure + any OpenAI-compatible base.
const NEEDS_ENDPOINT = new Set(["azure", "openai_compatible"]);
// providers that DON'T return token logprobs → confidence dark (the honest ⚠ at provider-pick time).
const NO_LOGPROBS = new Set(["anthropic", "gemini", "bedrock"]);

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

export default function ProviderPicker({ onSaved }) {
  const [provider, setProvider] = useState("openai");
  const [key, setKey] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [model, setModel] = useState("");
  const [save, setSave] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  const needsEndpoint = NEEDS_ENDPOINT.has(provider);
  const noLogprobs = NO_LOGPROBS.has(provider);
  const perRoleOnly = provider !== "openai" && provider !== "azure"; // gemini/bedrock/openai_compat/anthropic

  const onProvider = (p) => { setProvider(p); setEndpoint(""); setModel(""); setSave({ state: "idle", msg: "" }); };

  const testSave = async () => {
    setSave({ state: "saving", msg: "testing…" });
    try {
      const r = await configProvider({
        plane: provider === "anthropic" ? "assistant" : "grading",
        provider, api_key: key.trim(),
        endpoint: endpoint.trim() || undefined, model: model.trim() || undefined,
      });
      setSave({ state: "saved", msg: `Connected · tested ${r.last_tested || ""}` });
      setKey(""); // secret hygiene — clear the typed key on success (never re-render it)
      onSaved?.();
    } catch (e) {
      setSave({ state: "error", msg: String(e.message || e) });
    }
  };

  const canSave = !!key.trim() && (!needsEndpoint || !!endpoint.trim());
  const saveColor = save.state === "error" ? "var(--amber)" : "var(--teal)";

  return (
    <section data-testid="provider-picker-section"
      style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, border: "1px solid var(--border)", borderRadius: 10, background: "var(--surface-muted)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>Provider</div>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>pick a provider · authenticate · its models join the pool below</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        <span style={labelStyle}>Provider</span>
        <select value={provider} onChange={(e) => onProvider(e.target.value)} aria-label="provider"
          data-testid="provider-picker" style={inputStyle}>
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>{p.label} ({p.id})</option>
          ))}
        </select>
        {perRoleOnly && (
          <div data-testid="provider-per-role-note" style={{ fontSize: 10.5, color: "var(--muted)" }}>
            {provider === "anthropic"
              ? "Anthropic drives the assistant; as a judge it binds per-role in the pool below."
              : "Per-role only — no global grading selector. Bind a judge to it in the pool below."}
          </div>
        )}
        {noLogprobs && (
          <div data-testid="provider-logprobs-hint" style={{ fontSize: 10.5, color: "var(--amber)" }}>
            ⚠ no logprobs — confidence will be dark for this provider (no calibrated per-token confidence)
          </div>
        )}
        {needsEndpoint && (
          <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} aria-label="endpoint"
            data-testid="provider-endpoint"
            placeholder={provider === "azure" ? "https://…azure endpoint (api_base)" : "https://…OpenAI-compatible api_base"}
            style={inputStyle} />
        )}
        <div style={{ display: "flex", gap: 6 }}>
          <input data-testid="provider-key" type="password" autoComplete="off" value={key}
            onChange={(e) => setKey(e.target.value)} placeholder="API key (write-only, masked)" style={inputStyle} />
          <input value={model} onChange={(e) => setModel(e.target.value)} aria-label="provider model"
            placeholder="model (optional)" style={{ ...inputStyle, width: 190 }} />
        </div>
        <div>
          <button data-testid="provider-test-save" onClick={testSave}
            disabled={save.state === "saving" || !canSave} style={btn(true)}>
            {save.state === "saving" ? "Testing…" : "Test & save"}
          </button>
        </div>
        {save.state !== "idle" && save.state !== "saving" && (
          <div data-testid="provider-save-msg" style={{ fontSize: 11.5, color: saveColor }}>{save.msg}</div>
        )}
      </div>
    </section>
  );
}
