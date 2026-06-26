/* ProviderSettings.jsx — CONNECT-AI-CONSOLIDATE-1: the 2-section "Connect AI" surface.

   Collapses the former 5-section panel (provider-pick + grading Simple/Advanced + model-pool +
   per-consumer bind + authoring assistant) into TWO:
     1 · Providers (ProvidersSection) — the ONLY place a key is entered (the broadened set;
         endpoint only for azure/openai_compatible). configProvider stores the key, no model.
     2 · Assign models (AssignModelsSection) — one model per consumer, FOUR rows: the 3 judges +
         a now-COMPULSORY cross-provider chat_assistant; each {provider · model} pick →
         bindRole(role, provider, model), REUSING the provider's stored key (keys entered once).

   The connected-provider list + per-consumer bindings come from getRoleBindings ({roles,
   connected_providers}, never a key). Conversational-first holds: PASSIVE rail chrome — it never
   operates panes / the top-bar to advance the product. Inline styles on the shell CSS vars. */
import { useCallback, useEffect, useState } from "react";
import { Icon } from "../icons.jsx";
import { getRoleBindings } from "../bff.js";
import ProvidersSection from "./ProvidersSection.jsx";
import AssignModelsSection from "./AssignModelsSection.jsx";

const btn = (primary) => ({
  padding: "6px 12px", fontSize: 12, borderRadius: 6, border: "none", cursor: "pointer",
  background: primary ? "var(--accent)" : "var(--surface-muted)",
  color: primary ? "#fff" : "var(--ink)", fontWeight: 600,
});

export default function ProviderSettings({ onClose }) {
  const [bindings, setBindings] = useState({ roles: {}, connected_providers: [] });

  const refresh = useCallback(() => {
    getRoleBindings()
      .then((b) => setBindings(b || { roles: {}, connected_providers: [] }))
      .catch(() => {});
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const connected = bindings.connected_providers || [];
  const roles = bindings.roles || {};

  return (
    <div data-testid="provider-settings" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="link" size={16} /></span>
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>Connect AI</div>
        <span style={{ fontSize: 11.5, color: "var(--muted)" }}>enter each key once in Providers · assign a model to each reviewer · your key is stored securely and never shown again</span>
        {onClose && (
          <button data-testid="provider-settings-close" aria-label="Close" onClick={onClose}
            style={{ marginLeft: "auto", ...btn(false), padding: "4px 8px", display: "inline-flex", alignItems: "center" }}>
            <Icon name="close" size={14} />
          </button>
        )}
      </div>

      <ProvidersSection connected={connected} onSaved={refresh} />
      <AssignModelsSection connected={connected} bindings={roles} onBound={refresh} />
    </div>
  );
}
