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

// The config tool primitives: 5 §5b widgets + agent_editor/audit_log (UAP-1) +
// judge_editor (UAP-2) + run_panel (UAP-3) + judge_builder (PHASE2-WIRE — the inline
// create-a-new-judge card). Authoritative key list (drives the A2 registry test + the
// W3 dedup/intent gating).
export const KNOWN_TOOLS = [
  "tool-flag_editor",
  "tool-contract_builder",
  "tool-kb_picker",
  "tool-verdict_card",
  "tool-calibration_chart",
  "tool-agent_editor",
  "tool-audit_log",
  "tool-judge_editor",
  "tool-run_panel",
  "tool-case_summary",
  "tool-judge_builder",
  "tool-criterion_builder",
  "tool-scorecard",
  "tool-ingest_preview",
  "tool-tool_builder",
  "tool-readiness_card",
  "tool-reliability_card",
  "tool-sweep_card",
  "tool-criterion_jute_builder",
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
   - unknown type     → fallback

   LOCKED prop convention (S-BS-19 / fresh-critic Ambiguity-2): part.output is SPREAD
   as props ({...part.output}), plus `part` and any handlers (e.g. onResult). Every
   component — datapoint cards AND input widgets — destructures the specific fields it
   needs directly from props. NO {data}/{output} wrapper. So a datapoint's payload is
   `part.output = {confidence, verdict, …}` (flat), never `{data: {…}}`. VerdictCard +
   CalibrationChart both conform to this flat-spread shape. */
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
