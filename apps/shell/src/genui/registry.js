/* registry.js — the generative-UI tool→component protocol (SPEC §5b / §6.2).

   Generative UI = a typed "tool" part (tool-<name>) → a registered React component.
   We follow the Vercel AI SDK message-`parts` shape (plan-review decision 4): the
   conversational engine emits parts like
       { type: "tool-flag_editor", state: "output-available", output: {...} }
   and renderTool(part) resolves the component when state === "output-available".
   No chat-framework dependency this phase (scripted-default, §5c — zero LLM); a
   live host (assistant-ui / AI SDK useChat) can layer on later without touching
   the components, since they only depend on this registry contract.

   Components self-register via registerTool() at module load; genui/index.js is the
   barrel that imports them (triggering registration) and re-exports renderTool.

   This file is .js (per the driver deliverable name), so it builds React elements
   via createElement rather than JSX. */
import { createElement as h } from "react";

// The 5 §5b config primitives. Authoritative key list (drives the A2 registry test).
export const KNOWN_TOOLS = [
  "tool-flag_editor",
  "tool-contract_builder",
  "tool-kb_picker",
  "tool-verdict_card",
  "tool-calibration_chart",
];

const TOOL_REGISTRY = {};

export function registerTool(toolName, Component) {
  TOOL_REGISTRY[toolName] = Component;
}

export function getTool(toolName) {
  return TOOL_REGISTRY[toolName] ?? null;
}

const NOTE_BASE =
  "rounded-[var(--radius)] border border-border bg-secondary px-3.5 py-3 text-xs font-[family-name:var(--font-mono)]";

/* Unknown / unregistered tool → graceful fallback (never throws, never blank). */
function toolFallback(type) {
  return h(
    "div",
    { className: `${NOTE_BASE} border-dashed border-border-strong text-muted-foreground` },
    "Unsupported component: ",
    h("span", { className: "text-foreground" }, type || "unknown"),
  );
}

/* renderTool(part, handlers?) — the single render entrypoint.
   - output-available → the registered component (props = part.output + handlers)
   - output-error     → an inline error note
   - input states     → a lightweight "preparing" placeholder
   - unknown type     → fallback */
export function renderTool(part, handlers = {}) {
  if (!part || typeof part.type !== "string") return toolFallback(part?.type);

  const Component = getTool(part.type);
  if (!Component) return toolFallback(part.type);

  if (part.state === "output-error") {
    return h(
      "div",
      { className: `${NOTE_BASE} text-[color:var(--accent-ink)]` },
      part.errorText || "Tool failed to produce output.",
    );
  }

  if (part.state && part.state !== "output-available") {
    return h("div", { className: `${NOTE_BASE} text-muted-foreground` }, `Preparing ${part.type}…`);
  }

  return h(Component, { ...(part.output || {}), part, ...handlers });
}
