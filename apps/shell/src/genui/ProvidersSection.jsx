/* ProvidersSection.jsx — CONNECT-AI-CONSOLIDATE-1, Section 1: the ONLY place a key is entered.

   Pick a PROVIDER from the broadened set (openai · anthropic · azure · gemini · bedrock ·
   openai-compatible), supply a masked key (+ an endpoint where the provider needs one — azure /
   openai_compatible api_base), Test & save (REUSES configProvider — the same POST /v1/provider/config
   that test-probes the key read-only then writes it write-only, NO model). The secret rides a password
   input and is CLEARED on success (never echoed). Below: the CONNECTED-providers list (the
   getRoleBindings connected_providers) with a status dot + the ⚠ no-logprobs hint per provider
   (anthropic/gemini/bedrock). NO model field here — model assignment is Section 2 (Assign models).
   PASSIVE rail chrome — never operates panes / the top-bar. Inline styles on the shell CSS vars. */
import { useState } from "react";
import { configProvider } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { friendlyError } from "./copy.js";

const PROVIDERS = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Anthropic" },
  { id: "azure", label: "Azure OpenAI" },
  { id: "gemini", label: "Gemini" },
  // bedrock: API Literal still accepts it, but the single-key form can't carry AWS
  // secret-key/region — hidden from the picker until multi-field auth lands.
  { id: "openai_compatible", label: "OpenAI-compatible" },
  // F8-PROVIDER: a purpose-built eval reward model in the commodity judge slot — score→verdict
  // is deterministic threshold logic; graded raw scores ride scores_raw (no logprobs).
  { id: "composo", label: "Composo (reward model)" },
];
const NEEDS_ENDPOINT = new Set(["azure", "openai_compatible"]);
// providers that DON'T return token logprobs → confidence dark (the honest ⚠).
export const NO_LOGPROBS = new Set(["anthropic", "gemini", "bedrock", "composo"]);

const inputStyle = {
  padding: "6px 8px", fontSize: 12.5, borderRadius: 6, border: "1px solid var(--border)",
  background: "var(--bg)", color: "var(--ink)", width: "100%", boxSizing: "border-box",
};
const labelStyle = { fontSize: 11, color: "var(--muted)", fontWeight: 600 };

export default function ProvidersSection({ connected = [], onSaved }) {
  const [provider, setProvider] = useState("openai");
  const [key, setKey] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [apiVersion, setApiVersion] = useState(""); // CONNECT-AI-AZURE-1: OPTIONAL azure api-version
  const [save, setSave] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  const needsEndpoint = NEEDS_ENDPOINT.has(provider);
  const isAzure = provider === "azure";
  const onProvider = (p) => { setProvider(p); setEndpoint(""); setApiVersion(""); setSave({ state: "idle", msg: "" }); };

  const testSave = async () => {
    setSave({ state: "saving", msg: "testing…" });
    try {
      // anthropic rides the assistant plane (the Agent-SDK ping); everything else grades — exactly
      // as the prior provider-first picker. NO model — model assignment is Section 2. Azure may
      // carry an OPTIONAL api_version (CONNECT-AI-AZURE-1; non-azure providers never send it).
      const r = await configProvider({
        plane: provider === "anthropic" ? "assistant" : "grading",
        provider, api_key: key.trim(),
        endpoint: endpoint.trim() || undefined,
        ...(isAzure && apiVersion.trim() ? { api_version: apiVersion.trim() } : {}),
      });
      setSave({ state: "saved", msg: `Connected · tested ${r.last_tested || ""}` });
      setKey(""); // secret hygiene — clear the typed key on success (never re-render it)
      onSaved?.();
    } catch (e) {
      setSave({ state: "error", msg: friendlyError(e) });
    }
  };

  const canSave = !!key.trim() && (!needsEndpoint || !!endpoint.trim());
  // an error is a failure (red --accent), not a warning (amber); success stays teal.
  const saveColor = save.state === "error" ? "var(--accent)" : "var(--teal)";

  return (
    <section data-testid="providers-section"
      style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, border: "1px solid var(--border)", borderRadius: 10, background: "var(--surface-muted)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>1 · Providers</div>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>connect a provider with a key — the one place a key is entered</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        <span style={labelStyle}>Provider</span>
        <select value={provider} onChange={(e) => onProvider(e.target.value)} aria-label="provider"
          data-testid="providers-provider" style={inputStyle}>
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>{p.label} ({p.id})</option>
          ))}
        </select>
        {NO_LOGPROBS.has(provider) && (
          <div data-testid="providers-logprobs-hint" style={{ fontSize: 10.5, color: "var(--amber)" }}>
            ⚠ this provider doesn't report a confidence signal — models from it won't show a confidence number
          </div>
        )}
        {needsEndpoint && (
          <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} aria-label="endpoint"
            data-testid="providers-endpoint"
            placeholder={provider === "azure" ? "Azure endpoint URL" : "Endpoint URL (OpenAI-compatible)"}
            style={inputStyle} />
        )}
        {isAzure && (
          <input value={apiVersion} onChange={(e) => setApiVersion(e.target.value)} aria-label="api version"
            data-testid="providers-api-version" placeholder="API version (optional · default 2024-10-21)"
            style={inputStyle} />
        )}
        <input data-testid="providers-key" type="password" autoComplete="off" value={key}
          onChange={(e) => setKey(e.target.value)} placeholder="API key (stored securely, never shown again)" style={inputStyle} />
        <div>
          <Button size="sm" data-testid="providers-save" onClick={testSave}
            disabled={save.state === "saving" || !canSave}
            title={!canSave ? "Enter your API key" + (needsEndpoint ? " and the endpoint URL" : "") + " first" : undefined}>
            {save.state === "saving" ? "Testing…" : "Test & save"}
          </Button>
        </div>
        {save.state !== "idle" && save.state !== "saving" && (
          <div data-testid="providers-save-msg" style={{ fontSize: 11.5, color: saveColor }}>{save.msg}</div>
        )}
      </div>

      {/* ── Connected providers (those with a stored key) ── */}
      <div data-testid="providers-connected" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={labelStyle}>Connected</span>
        {connected.length === 0 ? (
          <div style={{ fontSize: 11.5, color: "var(--muted)" }}>No providers connected yet — add one above.</div>
        ) : (
          connected.map((p) => (
            <div key={p} data-testid={`providers-connected-row-${p}`}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 9px", border: "1px solid var(--border)", borderRadius: 8, background: "var(--bg)" }}>
              <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--teal)" }} />
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--mono)" }}>{p}</span>
              {NO_LOGPROBS.has(p) && (
                <span style={{ fontSize: 10.5, color: "var(--amber)" }}>⚠ no logprobs</span>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
