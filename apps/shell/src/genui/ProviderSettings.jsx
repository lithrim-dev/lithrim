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
import { Button } from "../components/ui/button.jsx";
import ProvidersSection from "./ProvidersSection.jsx";
import AssignModelsSection from "./AssignModelsSection.jsx";

export default function ProviderSettings({ onClose, agent }) {
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
          <Button variant="ghost" size="icon" className="ml-auto h-7 w-7"
            data-testid="provider-settings-close" aria-label="Close" onClick={onClose}>
            <Icon name="close" size={14} />
          </Button>
        )}
      </div>

      {/* F4: providers + role bindings are shared across ALL workspaces (adding a key IS the CE
          onboarding) — a subtle one-line clarity note so a "fresh" workspace's pre-connected
          provider doesn't read as a bug. Muted-hint style, matching the header subtitle. */}
      <div data-testid="provider-scope-hint" style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.4, marginTop: -4 }}>
        Providers and reviewer model assignments are shared across all your workspaces.
      </div>

      <ProvidersSection connected={connected} onSaved={refresh} />
      <AssignModelsSection connected={connected} bindings={roles} onBound={refresh} agent={agent} />
    </div>
  );
}
