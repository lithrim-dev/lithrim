/* AssignModelsSection.jsx — CONNECT-AI-CONSOLIDATE-1 / CONNECT-AI-AZURE-1: one model per consumer.

   FOUR rows — risk_judge, policy_judge, faithfulness_judge, and a now-COMPULSORY chat_assistant
   (CONV-RUNTIME-1 made the chat runtime provider-agnostic, so chat is CROSS-PROVIDER now). Each row
   is a {provider · model} picker: a provider <select> (connected providers) + a model <input
   list=datalist> that offers that provider's catalog presets AND accepts FREE TEXT — so a
   deployment-based provider (Azure) whose catalog is {models:[]} can have its deployment TYPED, not
   only picked (CONNECT-AI-AZURE-1, the EMPTY-picker fix). → bindRole(role, provider, model) which
   REUSES the provider's stored key (no re-keying). The ✓ assigned state reads from getRoleBindings;
   a no-logprobs model surfaces the ⚠ hint at pick time. A "use one model for all judges" shortcut
   binds the 3 judge rows in one pick. A setup-complete status requires all 3 judges AND
   chat_assistant (the compulsory-chat gate). PASSIVE rail chrome — never operates panes / the
   top-bar. Inline styles on the shell CSS vars. */
import { useEffect, useState } from "react";
import { getModelCatalog, bindRole, getCouncilRoster, setCouncilRoster } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { NO_LOGPROBS } from "./ProvidersSection.jsx";
import { roleLabel, roleLabelsFor, friendlyError } from "./copy.js";

// R2a fallback ONLY: the rows derive from the ACTIVE workspace roster (getCouncilRoster's
// selectable — JudgeBuilder-authored roles included); the v2 trio renders only until/unless
// the roster loads empty (offline / first paint).
const FALLBACK_JUDGE_ROLES = ["risk_judge", "policy_judge", "faithfulness_judge"];

const inputStyle = {
  padding: "6px 8px", fontSize: 12.5, borderRadius: 6, border: "1px solid var(--border)",
  background: "var(--bg)", color: "var(--ink)", width: "100%", boxSizing: "border-box",
};
const labelStyle = { fontSize: 11, color: "var(--muted)", fontWeight: 600 };
// CONNECT-AI-LAYOUT-1: every consumer row shares ONE column grid so label · provider · model · action
// align across rows; minmax(_,1fr) lets the model input flex (never the variable status label starving
// it). The assigned `✓ provider · model` status is lifted to its OWN line (STATUS_INDENT) so a long
// model id wraps there instead of crushing the controls / forcing the modal to scroll horizontally.
const ROW_GRID = {
  display: "grid", gridTemplateColumns: "150px 128px minmax(120px, 1fr) auto",
  alignItems: "center", gap: 8,
};
const STATUS_INDENT = 158; // align status / hints under the controls (150 label + 8 gap)

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

export default function AssignModelsSection({ connected = [], bindings = {}, onBound, agent }) {
  const [catalog, setCatalog] = useState({ providers: {} });
  // per-role picked {provider, model} (free-text model). The "all judges" shortcut is keyed under "*".
  const [sel, setSel] = useState({});
  const [msg, setMsg] = useState({});
  // REVIEWER-MODE: how many reviewers run on a grade — `panel` is the active pack's full reviewer
  // roster (panel default); `single` rosters exactly `singleRole`. Persisted on the agent via
  // setCouncilRoster (null = panel, [role] = single).
  const [panel, setPanel] = useState([]);
  // GENERALIST-1: the single-reviewer OPTIONS — the panel + any opt-in lens role (e.g. a generalist
  // carrying the full-coverage lens) that runs ONLY via an explicit single roster, never the panel.
  const [selectable, setSelectable] = useState([]);
  const [reviewerMode, setReviewerMode] = useState("panel");
  const [singleRole, setSingleRole] = useState("");
  // R2b: the CUSTOM subset roster (any N of the selectable reviewers — the N-clone council).
  const [customRoster, setCustomRoster] = useState([]);
  // the persisted override (null = panel) — drives the honest ready gate (R2a).
  const [activeRoster, setActiveRoster] = useState(null);
  const [rosterMsg, setRosterMsg] = useState("");
  // CE-JUDGE-RECOMMEND-1: the deterministic panel-vs-single-Generalist recommendation from the
  // pack's reviewer structure ({mode, reviewer, k, rationale}); rendered as guidance, one-click apply.
  const [recommendation, setRecommendation] = useState(null);

  useEffect(() => {
    getModelCatalog({ live: false }).then((c) => setCatalog(c || { providers: {} })).catch(() => {});
  }, []);

  useEffect(() => {
    getCouncilRoster(agent).then((r) => {
      const pnl = r?.panel || [];
      setPanel(pnl);
      setSelectable(r?.selectable || pnl);
      setRecommendation(r?.recommendation || null);
      const rr = r?.reviewer_roster;
      setActiveRoster(rr && rr.length ? rr : null);
      if (rr && rr.length > 1) { setReviewerMode("custom"); setCustomRoster(rr); setSingleRole(rr[0]); }
      else if (rr && rr.length === 1) { setReviewerMode("single"); setSingleRole(rr[0]); setCustomRoster(rr); }
      else { setReviewerMode("panel"); setSingleRole(pnl[0] || ""); setCustomRoster([]); }
    }).catch(() => {});
  }, [agent]);

  const saveRoster = async (roster) => {
    setRosterMsg("saving…");
    try {
      await setCouncilRoster({ agent, roster });
      setActiveRoster(roster && roster.length ? roster : null);
      setRosterMsg(
        !roster || !roster.length ? "panel"
          : roster.length === 1 ? `single → ${roleLabel(roster[0])}`
            : `custom → ${roster.length} reviewers`,
      );
      onBound?.();
    }
    catch (e) { setRosterMsg(String(e.message || e)); }
  };
  const applyReviewerMode = (m) => {
    setReviewerMode(m);
    if (m === "single") saveRoster([singleRole || panel[0]]);
    else if (m === "panel") saveRoster(null);
    // custom: no immediate save — an empty subset would clear to panel; the checkboxes save.
  };
  const applySingleRole = (role) => { setSingleRole(role); saveRoster([role]); };

  // R2a: the reviewer rows = the ACTIVE workspace's bindable reviewers (panel ∪ selectable —
  // authored roles included); the v2 trio only as the empty-roster fallback.
  const judgeRoles = (() => {
    const seen = new Set();
    const merged = [...panel, ...selectable].filter((r) => !seen.has(r) && seen.add(r));
    return merged.length ? merged : FALLBACK_JUDGE_ROLES;
  })();
  const allRoles = [...judgeRoles, "chat_assistant"];
  // DUP-ROLE-LABEL-1: colliding pretty labels (generalist_judge vs generalist_reviewer) render
  // with their role id appended so every picker row stays distinguishable.
  const rowLabel = roleLabelsFor(allRoles);

  // R2b: toggle one reviewer in the custom subset (kept in selectable order, deterministic).
  const toggleRosterRole = (role) => {
    const next = customRoster.includes(role)
      ? customRoster.filter((r) => r !== role)
      : judgeRoles.filter((r) => customRoster.includes(r) || r === role);
    setCustomRoster(next);
    saveRoster(next.length ? next : null);
  };

  // CONNECT-AI-PREFILL-1: seed each row's picker from its SAVED binding so an already-configured role
  // shows its provider+model in the editable controls (not an empty field next to a ✓). Only seed a row
  // the user hasn't touched (absent from `sel`) — never clobber an in-progress edit; no-op once seeded.
  useEffect(() => {
    setSel((s) => {
      let changed = false;
      const next = { ...s };
      for (const role of allRoles) {
        const b = bindings?.[role];
        if (b?.provider && next[role] === undefined) {
          next[role] = { provider: b.provider, model: b.model || "" };
          changed = true;
        }
      }
      return changed ? next : s;
    });
  }, [bindings, panel, selectable]); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (key) => sel[key] || { provider: "", model: "", endpoint: "", api_version: "" };
  const setProvider = (key, provider) =>
    setSel((s) => ({ ...s, [key]: { ...pick(key), provider } }));
  const setModel = (key, model) =>
    setSel((s) => ({ ...s, [key]: { ...pick(key), model } }));
  // NEW-G1: the OPTIONAL per-role endpoint (api_base) + api_version — only meaningful for a
  // deployment-endpoint provider (azure / openai_compatible), passed to bindRole when set.
  const setEndpoint = (key, endpoint) =>
    setSel((s) => ({ ...s, [key]: { ...pick(key), endpoint } }));
  const setApiVersion = (key, api_version) =>
    setSel((s) => ({ ...s, [key]: { ...pick(key), api_version } }));
  // NEW-G1: the providers whose per-role endpoint/api_version inputs are shown (deployment-based).
  const wantsEndpoint = (provider) => provider === "azure" || provider === "openai_compatible";

  const doBind = async (role, provider, model, endpoint, api_version) => {
    setMsg((m) => ({ ...m, [role]: { kind: "pending", text: "Binding…" } }));
    try {
      await bindRole({ role, provider, model, endpoint, api_version });
      setMsg((m) => ({ ...m, [role]: { kind: "ok", text: `Bound → ${provider} · ${model}` } }));
      onBound?.();
    } catch (e) {
      setMsg((m) => ({ ...m, [role]: { kind: "err", text: friendlyError(e) } }));
    }
  };

  const canBind = (key) => { const p = pick(key); return !!p.provider && !!p.model.trim(); };
  // NEW-G1: thread the per-role endpoint/api_version (trimmed → undefined when blank, so the
  // bind body omits them and falls back to the stored global — back-compat).
  const bindRow = (role) => {
    const p = pick(role);
    if (!canBind(role)) return;
    doBind(role, p.provider, p.model.trim(),
      (p.endpoint || "").trim() || undefined, (p.api_version || "").trim() || undefined);
  };
  const bindAllJudges = () => {
    const p = pick("*");
    if (!canBind("*")) return;
    for (const role of judgeRoles)
      doBind(role, p.provider, p.model.trim(),
        (p.endpoint || "").trim() || undefined, (p.api_version || "").trim() || undefined);
  };

  // R2a — the HONEST readiness gate: the reviewers that will ACTUALLY grade (the persisted
  // roster override when set, else the panel/rows) must each be bound, plus chat_assistant.
  const isBound = (role) => !!bindings?.[role]?.provider;
  const requiredJudges = activeRoster && activeRoster.length ? activeRoster : judgeRoles;
  const judgesBound = requiredJudges.filter(isBound).length;
  const chatBound = isBound("chat_assistant");
  const boundCount = judgesBound + (chatBound ? 1 : 0);
  const totalRequired = requiredJudges.length + 1;
  const ready = judgesBound === requiredJudges.length && requiredJudges.length > 0 && chatBound;

  // one provider <select> + a model <input list=datalist> (presets + free text). `key` namespaces
  // the row (a role or "*" for the all-judges shortcut); `idPrefix` is the datalist + testid stem.
  const pickerControls = (key, idPrefix) => {
    const p = pick(key);
    const presets = presetsFor(catalog, p.provider);
    const listId = `${idPrefix}-modellist-${key}`;
    return (
      <>
        <select value={p.provider} onChange={(e) => setProvider(key, e.target.value)}
          aria-label={`${key} provider`} data-testid={`${idPrefix}-provider-${key}`}
          style={inputStyle}>
          <option value="">— provider —</option>
          {connected.map((cp) => (<option key={cp} value={cp}>{cp}</option>))}
        </select>
        <input value={p.model} onChange={(e) => setModel(key, e.target.value)}
          aria-label={`${key} model`} data-testid={`${idPrefix}-model-${key}`}
          list={listId} placeholder="model name" autoComplete="off" style={inputStyle} />
        <datalist id={listId} data-testid={`${idPrefix}-modellist-${key}`}>
          {presets.map((m) => (
            <option key={m.model} value={m.model}>{m.logprobs ? "" : "⚠ no logprobs"}</option>
          ))}
        </datalist>
      </>
    );
  };

  return (
    <section data-testid="assign-models-section"
      style={{ display: "flex", flexDirection: "column", gap: 12, padding: 12, border: "1px solid var(--border)", borderRadius: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>2 · Assign models</div>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>one model per reviewer · type your Azure model name · uses your saved key</span>
      </div>

      {/* ── REVIEWER-MODE: single reviewer vs the full panel (how many reviewers grade) ── */}
      {panel.length > 0 && (
        <div data-testid="reviewer-mode" style={{ display: "flex", flexDirection: "column", gap: 6, paddingBottom: 10, borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={labelStyle}>reviewers per grade</span>
            <Button data-testid="reviewer-mode-panel" size="sm" className="whitespace-nowrap"
              variant={reviewerMode === "panel" ? "default" : "outline"} onClick={() => applyReviewerMode("panel")}>Panel · {panel.length}</Button>
            <Button data-testid="reviewer-mode-single" size="sm" className="whitespace-nowrap"
              variant={reviewerMode === "single" ? "default" : "outline"} onClick={() => applyReviewerMode("single")}>Single reviewer</Button>
            <Button data-testid="reviewer-mode-custom" size="sm" className="whitespace-nowrap"
              variant={reviewerMode === "custom" ? "default" : "outline"} onClick={() => applyReviewerMode("custom")}>Custom</Button>
            {reviewerMode === "single" && (
              <select data-testid="reviewer-single-role" value={singleRole}
                onChange={(e) => applySingleRole(e.target.value)} aria-label="single reviewer" style={inputStyle}>
                {(selectable.length ? selectable : panel).map((r) => (<option key={r} value={r}>{rowLabel[r] || roleLabel(r)}</option>))}
              </select>
            )}
          </div>
          {/* R2b: any subset of the bindable reviewers — the N-clone council (e.g. one shared
              prompt across N models). Checking saves; unchecking all reverts to the panel. */}
          {reviewerMode === "custom" && (
            <div data-testid="reviewer-custom-roster" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {judgeRoles.map((r) => (
                <label key={r} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--ink)" }}>
                  <input type="checkbox" data-testid={`roster-check-${r}`}
                    checked={customRoster.includes(r)} onChange={() => toggleRosterRole(r)} />
                  {rowLabel[r] || roleLabel(r)}
                </label>
              ))}
            </div>
          )}
          <span style={{ fontSize: 10.5, color: "var(--muted)" }}>
            {reviewerMode === "single"
              ? `Only ${roleLabel(singleRole)} grades — fastest first pass; that reviewer's vote is the verdict.`
              : reviewerMode === "custom"
                ? `Exactly the checked reviewers grade${customRoster.length ? ` (${customRoster.length})` : " — check at least one"}.`
                : `All ${panel.length} reviewers grade — the panel needs ≥2 to reach consensus.`}
            {rosterMsg && <span> · {rosterMsg}</span>}
          </span>
          {/* CE-JUDGE-RECOMMEND-1: a deterministic recommendation from the pack's reviewer structure */}
          {recommendation && (
            <div data-testid="reviewer-recommendation" style={{ display: "flex", alignItems: "baseline", gap: 6, flexWrap: "wrap", fontSize: 10.5, color: "var(--muted)" }}>
              <span style={{ color: "var(--ink)", fontWeight: 600 }}>
                Recommended: {recommendation.mode === "panel" ? `Panel · ${panel.length}` : `Single · ${roleLabel(recommendation.reviewer)}${recommendation.k ? ` (k=${recommendation.k})` : ""}`}
              </span>
              <span>— {recommendation.rationale}</span>
              {((recommendation.mode === "panel" && reviewerMode !== "panel") ||
                (recommendation.mode === "single" && (reviewerMode !== "single" || singleRole !== recommendation.reviewer))) && (
                <Button data-testid="reviewer-apply-recommendation" size="sm" variant="secondary" className="h-5 px-2 text-[10px]"
                  onClick={() => { if (recommendation.mode === "panel") applyReviewerMode("panel"); else { setReviewerMode("single"); if (recommendation.reviewer) applySingleRole(recommendation.reviewer); else applyReviewerMode("single"); } }}>Use this</Button>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── use one model for all judges shortcut ── */}
      <div style={ROW_GRID}>
        <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600 }}>use one model for all reviewers</span>
        {pickerControls("*", "all-judges")}
        <Button data-testid="all-judges-submit" size="sm" variant="secondary" className="whitespace-nowrap"
          onClick={bindAllJudges} disabled={!canBind("*")}
          title={!canBind("*") ? "Pick a provider and model above first" : undefined}>Apply to {judgeRoles.length} reviewers</Button>
      </div>

      {/* ── the consumer rows: every bindable reviewer (roster-derived, R2a) + chat ── */}
      {allRoles.map((role) => {
        const p = pick(role);
        const pickedLogprobs = p.provider && p.model ? modelLogprobs(catalog, p.provider, p.model) : true;
        const bound = bindings?.[role];
        const isChat = role === "chat_assistant";
        return (
          <div key={role} data-testid={`role-bind-row-${role}`}
            style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={ROW_GRID}>
              <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--mono)" }}>
                {rowLabel[role] || roleLabel(role)}
                {isChat && <span style={{ marginLeft: 6, fontSize: 9.5, fontWeight: 700, color: "var(--accent)", textTransform: "uppercase" }}>required</span>}
              </span>
              {pickerControls(role, "role-bind")}
              <Button data-testid={`role-bind-submit-${role}`} size="sm" className="whitespace-nowrap"
                onClick={() => bindRow(role)} disabled={!canBind(role)}
                title={!canBind(role) ? "Pick a provider and model first" : undefined}>Assign</Button>
            </div>
            {/* NEW-G1: the OPTIONAL per-role endpoint + api_version — only for a deployment-endpoint
                provider (azure / openai_compatible); blank → the stored global (back-compat). */}
            {wantsEndpoint(p.provider) && (
              <div style={{ display: "grid", gridTemplateColumns: "minmax(120px, 1fr) 140px", gap: 8, paddingLeft: STATUS_INDENT }}>
                <input value={p.endpoint || ""} onChange={(e) => setEndpoint(role, e.target.value)}
                  aria-label={`${role} endpoint`} data-testid={`role-bind-endpoint-${role}`}
                  placeholder="endpoint (optional — else your saved one)" autoComplete="off" style={inputStyle} />
                <input value={p.api_version || ""} onChange={(e) => setApiVersion(role, e.target.value)}
                  aria-label={`${role} api version`} data-testid={`role-bind-apiversion-${role}`}
                  placeholder="api version (optional)" autoComplete="off" style={inputStyle} />
              </div>
            )}
            {bound?.provider && (
              <span data-testid={`role-bind-assigned-${role}`}
                style={{ fontSize: 10.5, color: "var(--teal)", paddingLeft: STATUS_INDENT, wordBreak: "break-word" }}>
                ✓ {bound.provider} · {bound.model}
              </span>
            )}
            {p.provider && p.model && !pickedLogprobs && (
              <div data-testid={`role-bind-logprobs-hint-${role}`} style={{ fontSize: 10.5, color: "var(--amber)", paddingLeft: STATUS_INDENT }}>
                ⚠ this model doesn't report a confidence signal — "{p.provider} · {p.model}" won't show a confidence number
              </div>
            )}
            {msg[role] && (
              <span data-testid={`role-bind-msg-${role}`}
                style={{ fontSize: 10.5, paddingLeft: STATUS_INDENT,
                  color: msg[role].kind === "err" ? "var(--accent)" : msg[role].kind === "ok" ? "var(--teal)" : "var(--muted)" }}>
                {msg[role].text}
              </span>
            )}
          </div>
        );
      })}

      {/* ── the setup-complete (compulsory-chat) gate ── */}
      <div data-testid="setup-complete-status"
        style={{ fontSize: 11.5, fontWeight: 600, color: ready ? "var(--teal)" : "var(--amber)" }}>
        {ready
          ? `Ready — all ${totalRequired} set`
          : chatBound
            ? `Not ready — ${boundCount} of ${totalRequired} set (a reviewer still needs a model)`
            : `The assistant needs a model before you can chat — ${boundCount} of ${totalRequired} set`}
      </div>
    </section>
  );
}
