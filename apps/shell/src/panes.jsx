/* panes.jsx — left rail, center conversation (ported verbatim; placeholder mark → real logo). */
import { useRef, useState, useEffect, useLayoutEffect } from "react";
import { Icon } from "./icons.jsx";
import { Mark, Wordmark } from "./brand.jsx";
import { ConfigCard } from "./cards.jsx";
import { renderTool } from "./genui/index.js";
import { CostModal } from "./components/CostModal.jsx";
import { Markdown } from "./components/Markdown.jsx";
import ProviderSettings from "./genui/ProviderSettings.jsx"; // CE-PROVIDER-UI: the "Connect AI" provider-connect panel
import { STEPS } from "./data.jsx";
import { getConversation, putConversation, deleteConversation, hasStoredToken, logout, signIn, runEval, gradeCases, ingestPreview, getRoleBindings, getReliability, getReliabilitySweep } from "./bff.js"; // PERSIST-CONV: the durable-thread store; UI-LOGIN-1/SESSION-MENU-1: the runtime auth token + the proactive sign-in; CHAT-FRESH-GRADE-1: the cost-gated fresh grade; RUN-ALL-1: the cohort grade; CE-INGEST-FRONTDOOR-1: the upload front door; FIRST-CONTACT-1: the connect-the-assistant signpost; RELIABILITY-CARD-1: the ⌘K "Show reliability" read; SWEEP (RIGOR-1/Q1 NEW-G3): the "Reliability sweep" K-curve read
import { flagLabel, friendlyError } from "./genui/copy.js"; // UX-COPY: render flag codes as readable issue phrases; UX-COPY-ERR-1: calm, leak-free error lines

// A friendly DISPLAY name for an evaluation. The raw id (ws0_default / eval-N /
// <pack>_default) stays the id everywhere it matters — switching, deleting, the API,
// the React key — this only changes what a person reads.
export function agentLabel(name) {
  if (!name) return name;
  if (name === "ws0_default") return "Sample evaluation";
  let m = /^eval-(\d+)$/.exec(name);
  if (m) return `Evaluation ${m[1]}`;
  m = /^(.+)_default$/.exec(name); // e.g. healthcare_default -> "Healthcare evaluation"
  if (m) return m[1].charAt(0).toUpperCase() + m[1].slice(1).replace(/_/g, " ") + " evaluation";
  return name;
}

// S-BS-19: the scripted host emits INPUT tool-parts; each widget's onResult threads
// the collected config into local config-plane state (the §3 "the conversation writes
// the config plane" loop). Local state per decision #3 (Zustand deferred).
const SETUP_PARTS = [
  ["tool-flag_editor", "flags"],
  ["tool-contract_builder", "contract"],
  ["tool-kb_picker", "kb"],
];

/* ============================ LEFT RAIL ============================ */
// CRUD-1 (D4): the rail lists the REAL config-plane agents (GET /v1/agents) — click to
// switch, × to delete (audited). The seed default + the last agent hide their delete
// affordance (the BFF's 422 guards, reflected in the UI). "New evaluation" (the +)
// creates a fresh runnable blank agent and switches to it.
// SHEPHERD-1 (W1): the Setup journey is now the shepherd's PLAN surface — `steps`
// (derived from live config + run state, journey.js) drives each node's state and the
// "N / total" count. Absent the derived data (offline / pre-fetch) it falls back to the
// static STEPS template so the rail never renders blank.
export function LeftRail({ width, agents = [], activeAgent, onSwitchAgent, onDeleteAgent, onNewEval, steps, journeyCount }) {
  const planSteps = steps && steps.length ? steps : STEPS;
  const count = journeyCount || { done: planSteps.filter((s) => s.state === "done").length, total: planSteps.length };
  // SESSION-MENU-1: an always-on session control. BFF auth is reactive-only (a 401 raises the gate),
  // so on an open/local server there was no way to proactively sign in/out — and the footer "⋯" was a
  // dead button. This is passive rail chrome: it never operates panes/top-bar to advance the product.
  const [sessionMenu, setSessionMenu] = useState(false);
  // CE-PROVIDER-UI (Build B): the "Connect AI" provider-connect panel, opened from the session
  // menu. Passive rail chrome — a modal settings panel; it never operates panes/top-bar to advance.
  const [connectAI, setConnectAI] = useState(false);
  // FIRST-CONTACT-1: the empty-state "Connect AI" signpost (CenterPane) opens this modal via a
  // window event — settings chrome invoked from content, still never operating panes/top-bar.
  useEffect(() => {
    const open = () => setConnectAI(true);
    window.addEventListener("lithrim:connect-ai", open);
    return () => window.removeEventListener("lithrim:connect-ai", open);
  }, []);
  const closeConnectAI = () => {
    setConnectAI(false);
    window.dispatchEvent(new CustomEvent("lithrim:connect-ai-closed")); // CenterPane re-checks chat_ready
  };
  const authed = hasStoredToken();
  // DELETE-CONFIRM-1: a two-step in-DOM confirm before deleting an evaluation — deleting an agent
  // also drops its audit row, so a stray click must not destroy it (never window.confirm).
  const [confirmDelete, setConfirmDelete] = useState(null);
  return (
    <aside className="rail" style={{ width }}>
      <div className="rail-brand" style={{ display: "flex", alignItems: "center", height: 48, padding: "0 16px", borderBottom: "1px solid var(--border)", flex: "0 0 auto" }}>
        <Wordmark markSize={18} />
      </div>
      <div className="rail-sec">
        <div className="rail-hd">
          <span className="lbl">Evaluations</span>
          <button className="icon-btn" title="New evaluation" aria-label="New evaluation" onClick={onNewEval}><Icon name="plus" size={16} /></button>
        </div>
        {/* CMDK-1: was an inert div — now opens the command palette (App listens for the event). */}
        <button type="button" className="tb-cmd" style={{ position: "static", transform: "none", width: "100%", height: 32 }}
          title="Search cases & evaluations, or run a command (⌘K)"
          onClick={() => { try { window.dispatchEvent(new CustomEvent("lithrim:cmdk")); } catch { /* no-op */ } }}>
          <Icon name="search" size={14} /><span>Search</span><span className="kbd">⌘K</span>
        </button>
      </div>
      <div className="rail-scroll">
        <div style={{ padding: "8px 12px 8px" }}>
          {agents.length === 0 && (
            <div className="ts" style={{ padding: "10px 6px", color: "var(--muted)" }}>
              No evaluations yet — click + to start one.
            </div>
          )}
          {agents.map((name) => {
            const seed = name === "ws0_default";
            const canDelete = !seed && agents.length > 1;
            return (
              <div key={name} data-testid={`agent-row-${name}`}
                className={"thread" + (activeAgent === name ? " active" : "")}
                onClick={() => onSwitchAgent?.(name)}>
                <span className="st" style={{ background: activeAgent === name ? "var(--accent)" : "var(--border)" }} />
                <div className="tt">
                  <div className="ti" title={name}>{agentLabel(name)}</div>
                  <div className="ts">{seed ? "Sample · start here" : "Your evaluation"}</div>
                </div>
                {canDelete && (confirmDelete === name ? (
                  <span onClick={(e) => e.stopPropagation()} style={{ display: "flex", alignItems: "center", gap: 2, flex: "0 0 auto" }}>
                    <button className="icon-btn" data-testid={`agent-delete-confirm-${name}`} title="Confirm delete" aria-label={`Confirm delete ${name}`}
                      style={{ color: "var(--accent)" }}
                      onClick={(e) => { e.stopPropagation(); setConfirmDelete(null); onDeleteAgent?.(name); }}>
                      <Icon name="check" size={14} />
                    </button>
                    <button className="icon-btn" title="Keep" aria-label={`Cancel delete ${name}`}
                      onClick={(e) => { e.stopPropagation(); setConfirmDelete(null); }}>
                      <Icon name="close" size={14} />
                    </button>
                  </span>
                ) : (
                  <button className="icon-btn" title="Delete this evaluation" aria-label={`Delete ${name}`}
                    onClick={(e) => { e.stopPropagation(); setConfirmDelete(name); }}>
                    <Icon name="close" size={14} />
                  </button>
                ))}
              </div>
            );
          })}
        </div>
        <div className="journey">
          <div className="rail-hd" style={{ padding: "12px 6px 12px" }}>
            <span className="lbl">Setup journey</span>
            <span className="tm" style={{ fontFamily: "var(--mono)" }}>{count.done} / {count.total}</span>
          </div>
          {planSteps.map((s, i) => (
            <div key={s.name} className={"step " + s.state}>
              <div className="nodecol">
                {/* number REQUIRED steps only (s.num), matching the "done / total" counter —
                    positional i+1 numbered the optional KB step 4 and Review 6 in a "/ 5" journey. */}
                <div className="node">{s.state === "done" ? <Icon name="check" size={12} sw={2.4} /> : (s.num ?? "·")}</div>
                {i < planSteps.length - 1 && <div className="line" />}
              </div>
              <div className="body-txt">
                <div className="sname">{s.name}{s.state === "current" && <span className="pill-now">NOW</span>}</div>
                <div className="sdesc">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="rail-foot" style={{ position: "relative" }}>
        <div className="avatar">L</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="who">You</div>
          <div className="org">Local workspace</div>
        </div>
        {/* SESSION-MENU-1: the always-on session menu — the footer "⋯" now toggles a small popover
            with a proactive Sign in… / Sign out (folding in the old token-only key button). */}
        <button className="icon-btn" aria-label="Session menu" title="Session" onClick={() => setSessionMenu((v) => !v)}>
          <Icon name="dots" size={16} />
        </button>
        {sessionMenu && (
          <>
            <div data-testid="session-menu-backdrop" onClick={() => setSessionMenu(false)} style={{ position: "fixed", inset: 0, zIndex: 40 }} />
            <div role="menu" style={{ position: "absolute", right: 12, bottom: "calc(100% + 6px)", zIndex: 41, minWidth: 188, padding: 6, borderRadius: 10, background: "var(--panel)", border: "1px solid var(--border)", boxShadow: "0 8px 28px rgba(0,0,0,0.18)" }}>
              <div style={{ padding: "6px 8px", fontSize: 11.5, color: "var(--muted)", lineHeight: 1.4 }}>
                {authed ? "Signed in with an access token" : "Not signed in · server is open"}
              </div>
              {/* CE-PROVIDER-UI (Build B): a passive "Connect AI" entry — opens the provider-connect
                  panel (grading engine + authoring assistant). It never operates panes/top-bar. */}
              <button className="icon-btn" role="menuitem" onClick={() => { setSessionMenu(false); setConnectAI(true); }}
                style={{ width: "100%", justifyContent: "flex-start", height: 32, padding: "0 8px", fontSize: 13, color: "var(--text)" }}>
                Connect AI
              </button>
              {authed ? (
                <button className="icon-btn" role="menuitem" onClick={() => { setSessionMenu(false); logout(); }}
                  style={{ width: "100%", justifyContent: "flex-start", height: 32, padding: "0 8px", fontSize: 13, color: "var(--text)" }}>
                  Sign out
                </button>
              ) : (
                <button className="icon-btn" role="menuitem" onClick={() => { setSessionMenu(false); signIn(); }}
                  style={{ width: "100%", justifyContent: "flex-start", height: 32, padding: "0 8px", fontSize: 13, color: "var(--text)" }}>
                  Sign in…
                </button>
              )}
            </div>
          </>
        )}
        {/* CE-PROVIDER-UI (Build B): the "Connect AI" panel — a centered modal over a backdrop
            (reuses the session-menu backdrop idiom). Passive settings surface; closing it returns
            to the app, it never opens an artifact pane. */}
        {connectAI && (
          <>
            <div data-testid="connect-ai-backdrop" onClick={closeConnectAI}
              style={{ position: "fixed", inset: 0, zIndex: 60, background: "rgba(0,0,0,0.32)" }} />
            <div role="dialog" aria-label="Connect AI" data-testid="connect-ai-panel"
              style={{ position: "fixed", zIndex: 61, top: "50%", left: "50%", transform: "translate(-50%, -50%)",
                width: "min(620px, 92vw)", maxHeight: "86vh", overflowY: "auto", padding: 18, borderRadius: 14,
                background: "var(--bg)", border: "1px solid var(--border)", boxShadow: "var(--shadow-pop)" }}>
              <ProviderSettings onClose={closeConnectAI} agent={activeAgent} />
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

/* ============================ CENTER ============================ */
// CHATBIND-2: the artifact pane's 4 tabs (the focus_artifact directive contract) + their
// labels. ARTIFACT_TABS guards the directive in the shell (defense-in-depth; the BFF tool
// already rejects an unknown tab) so a bogus tab can never open the pane to a crash.
const ARTIFACT_TABS = ["case", "report", "judges", "config", "corpus"];
const TAB_LABELS = { case: "Case", report: "Report", judges: "Judges", config: "Setup", corpus: "Cases" };

// CONV-UX-1 (W1): the live "thinking / working stages" — map a tool name (the wire carries
// the SDK-MCP `mcp__lithrim__<tool>`) to a present-progressive human label. The events already
// stream (loop.py tool_call); the shell renders them as an ordered, running→done activity
// timeline so dead air reads as progress, not a freeze.
const TOOL_LABELS = {
  get_agent: "Reading the agent",
  assemble_agent: "Editing the reviewers",
  get_judge: "Reading the judge",
  author_judge: "Setting up the reviewer",
  create_judge: "Creating the reviewer",
  delete_judge: "Removing the reviewer",
  author_flag: "Editing the flag",
  create_flag: "Creating the flag",
  delete_flag: "Deleting the flag",
  add_grounding_contract: "Adding a grounding contract",
  run_eval: "Surfacing the cost-confirm",
  run_eval_pack: "Running a $0 replay batch",
  review_runs: "Reviewing the run history",
  list_cases: "Listing the cases",
  show_case: "Loading the case",
  focus_artifact: "Opening a panel",
  kb_context: "Looking up the policy",
  propose_live_run: "Surfacing the cost-confirm",
};
const toolLabel = (name) => {
  const short = String(name || "").replace(/^mcp__lithrim__/, "");
  return (TOOL_LABELS[short] || short.replace(/_/g, " ") || "Working") + "…";
};

// CONV-UX-1 (W3): gen-UI cards (tool-<name> in KNOWN_TOOLS) participate in dedup + intent
// gating; pane-control DIRECTIVES (open_artifact / propose_live_run) are special-cased traces,
// never cards. A friendly label for an `ondemand` collapsed read.
const PART_LABELS = {
  "tool-audit_log": "audit trail",
  "tool-agent_editor": "the agent",
  "tool-judge_editor": "the judge",
  "tool-judge_builder": "the new judge",
  "tool-criterion_builder": "the new check",
  "tool-flag_editor": "the ontology",
  "tool-verdict_card": "the verdict",
  "tool-case_summary": "the case",
};

// SHEPHERD-1 (W4): the per-step kickoff the next-incomplete-step chip fills into the
// composer (never auto-sent — intent stays the human's). Keyed by the journey.js step name.
// The KEYS must stay verbatim (matched against journey.js step names); only the values
// — what the person "says" when they click the chip — are humanized.
const STEP_PROMPTS = {
  Domain: "What kind of AI output do you want to grade?",
  Judges: "Set up the first judge that scores it",
  "Ground truth": "Add a fact-check the judges have to pass",
  "Knowledge base": "Connect reference docs the judges can check against",
  Run: "Run the evaluation and show me the verdict",
  Review: "Open the report so I can review the verdict",
};
const GUIDED_SETUP_PROMPT = "Help me set up my first evaluation from scratch";

// CHAT-FRESH-GRADE-1: project a run-eval RECORD into the verdict-card output, the SAME way the
// agent-emitted card is built (apps/bff/agent/adapter.py verdict_part) — so a fresh grade the human
// cost-confirmed renders the IDENTICAL inline VerdictCard the agent's run_eval card does. Mirrors
// verdict_part's fields: verdict/confidence/agreement/answer/votes/floorBlocks/faithfulness pillar.
function verdictShape(rec) {
  const composite = rec?.composite || {};
  const council = rec?.council || {};
  const votes = council.votes || [];
  const verdict = String(composite.verdict || composite.stage_verdict || "—");
  const findings = (composite.active_findings || []).map((f) =>
    typeof f === "object" && f ? String(f.flag_code || f.code || f) : String(f),
  );
  const n = votes.length;
  const agree = n
    ? votes.filter((v) => (v.vote || "").toLowerCase() === (votes[0].vote || "").toLowerCase()).length
    : 0;
  const confs = votes.map((v) => v.confidence).filter((c) => typeof c === "number");
  const conf = confs.length ? (confs.reduce((a, b) => a + b, 0) / confs.length).toFixed(2) : "—";
  const out = {
    id: rec?.pipeline_run_id || rec?.case_id || "run",
    verdict: verdict.toUpperCase(),
    confidence: conf,
    agreement: n ? `${agree} / ${n}` : "—",
    answer: findings.length ? `${findings.length} issue(s): ${findings.slice(0, 6).map(flagLabel).join(", ")}` : "No issues — this passes the quality gate.",
    runId: rec?.pipeline_run_id || "",
    votes: votes.map((v) => ({
      role: String(v.judge_role || v.role || "judge"),
      vote: String(v.vote || ""),
      ...(typeof v.confidence === "number" ? { confidence: v.confidence } : {}),
      ...(v.reason ? { reason: String(v.reason) } : {}),
      // independent-axes model: carry THIS reviewer's own variance + k (never aggregated).
      ...(typeof v.variance === "number" ? { variance: v.variance } : {}),
      ...(typeof v.k === "number" ? { k: v.k } : {}),
    })),
  };
  // the named case outcome (independent-axes rule table) — the PRIMARY headline.
  const caseOutcome = council.case_outcome || composite.case_outcome;
  if (caseOutcome) out.caseOutcome = String(caseOutcome);
  const floorBlocks = (composite.floor_adjustments || [])
    .filter((fa) => fa.action === "floor_block")
    .map((fa) => ({ flag: fa.flag, contract_type: fa.contract_type, contract: fa.contract, disposition: fa.disposition }));
  if (floorBlocks.length) out.floorBlocks = floorBlocks;
  // FLOOR-CLEAR-1: the symmetric attribution — findings a deterministic fact-check DISPROVED
  // (rec.grounded.suppressed), so a flagged case still PASSES. Mirrors adapter.py verdict_part so the
  // fresh (cost-confirmed) grade renders the SAME "Cleared by a fact-check" badge the agent card does.
  const floorClears = ((rec?.grounded || {}).suppressed || [])
    .filter((s) => s.code)
    // REL-OPS-1 O2: the terminology edition rides along when present (absent otherwise — pre-O2 shape).
    .map((s) => ({ flag: s.code, reason: s.reason, evidence: s.evidence, ...(s.terminology_edition != null ? { terminology_edition: s.terminology_edition } : {}) }));
  if (floorClears.length) out.floorClears = floorClears;
  const faith = votes.find((v) => String(v.judge_role || "").toLowerCase().includes("faith"));
  if (faith) {
    out.pillar = "Faithfulness";
    out.pillarStatus = ["PASS", "APPROVE"].includes(String(faith.vote || "").toUpperCase()) ? "clear ✓" : "flagged";
  }
  return out;
}

export function CenterPane({ onOpenArtifact, onOpenCaseRun, artifactOpen, onRunEval, runStatus, agent = "ws0_default", activeCase = null, onActiveCase, onRunResult, onConfigSaved, nextStepName, readiness = null }) {
  // config-plane state the input tool-parts write into (S-BS-19).
  const [setup, setSetup] = useState({});
  // SHEPHERD-1 (W3): the editor cards (Agent/Judge/Flag) already call onResult on a
  // successful audited Save (the approval gate). captureSetup is that save signal — fire
  // onConfigSaved so App.refreshJourney re-derives the rail (the step flips done) and the
  // shepherd's next turn re-reads the live config. The smallest possible callback; the
  // frozen card components are untouched (they already emit onResult).
  const captureSetup = (key) => (result) => {
    setSetup((s) => ({ ...s, [key]: result }));
    onConfigSaved?.();
  };
  const captured = Object.keys(setup);

  // UAP-5b / R11: the live conversational loop. The composer streams POST /v1/chat
  // (SSE); each event appends to `chat` — assistant text + tool-result gen-UI parts
  // (rendered via the EXISTING renderTool registry, no new cards). The agent drives
  // audited config writes + $0 replay runs; it can NEVER fire a paid run.
  const [chat, setChat] = useState([]); // [{role:'user'|'assistant', text?, parts?}]
  const [input, setInput] = useState("");
  // FIRST-CONTACT-1: the empty state funnels the first message into chat — if the assistant
  // can't answer (no chat provider AND no SDK path: the fresh Docker boot), say so BEFORE the
  // doomed send, with a real "Connect AI" opener. Optimistic default (banner only on a
  // confirmed not-ready); re-checked when the Connect AI modal closes. The optional-call guard
  // keeps older test mocks (no getRoleBindings export) green.
  const [chatReady, setChatReady] = useState(true);
  useEffect(() => {
    let on = true;
    const check = () => {
      // try/catch (not typeof): a vi.mock factory without this export throws on ACCESS.
      try {
        getRoleBindings().then((r) => { if (on && r) setChatReady(r.chat_ready !== false); }).catch(() => {});
      } catch { /* older test mocks / partial bff surfaces: keep the optimistic default */ }
    };
    check();
    window.addEventListener("lithrim:connect-ai-closed", check);
    return () => { on = false; window.removeEventListener("lithrim:connect-ai-closed", check); };
  }, []);
  const [sending, setSending] = useState(false);
  // PERSIST-CONV: the durable-thread guards. `hydrated` flips once the stored thread loads for
  // THIS agent (so the persist effect never writes back before the hydrate completes — no
  // empty-thread clobber of a stored one). CenterPane remounts per-agent on the sessionKey bump,
  // so a fresh mount = a fresh hydrate; the `agent` dep also re-hydrates a same-instance swap.
  const hydratedRef = useRef(null); // the agent the current chat was hydrated for
  const [clearing, setClearing] = useState(false); // PERSIST-CONV: in-DOM confirm for the destructive clear
  const [reloadTick, setReloadTick] = useState(0); // REFRESH-1: bump → rehydrate the thread from the durable store
  const [paid, setPaid] = useState({ open: false, busy: false }); // the in-DOM cost gate
  // COHORT-SUBSET-1: non-chat cohort triggers (the Cases-browser "Run selected", the ⌘K "Grade all")
  // reach the SAME in-DOM cohort cost-confirm the chat's propose_run_all opens — via the
  // `lithrim:grade-cohort` window bridge (the same CustomEvent idiom as lithrim:cmdk / connect-ai).
  // detail.case_ids (a subset) → gradeCases scopes to it; omit → ALL. The agent still never spends;
  // the human's confirm (confirmPaidRun, cohort branch) is the sole paid path.
  useEffect(() => {
    const onGradeCohort = (e) => {
      const ids = e?.detail?.case_ids;
      setPaid({ open: true, busy: false, cohort: true, caseIds: Array.isArray(ids) && ids.length ? ids : null });
    };
    window.addEventListener("lithrim:grade-cohort", onGradeCohort);
    return () => window.removeEventListener("lithrim:grade-cohort", onGradeCohort);
  }, []);
  // RELIABILITY-CARD-1: the ⌘K "Show reliability" trigger — fetch the REAL endpoint
  // (GET /v1/reliability/{agent}, $0 read) and render the tool-reliability_card INLINE as a
  // fresh assistant turn (the same registry card the agent would emit; conversational-first,
  // no new tab). The endpoint returns {agent, metrics, n_runs}; the card reads the flat-spread
  // metrics + n_runs. On an error/404/insufficient data the card's own honest empty state shows
  // (an empty output → "No graded runs yet"); NEVER a fabricated number, never a crash.
  useEffect(() => {
    const onShow = async () => {
      let output = {};
      try {
        const r = await getReliability(agent);
        output = { ...(r?.metrics || {}), n_runs: r?.n_runs ?? r?.metrics?.n_runs };
      } catch { output = {}; }
      setChat((c) => [
        ...c,
        { role: "assistant", text: "", parts: [{ type: "tool-reliability_card", state: "output-available", output }] },
      ]);
    };
    window.addEventListener("lithrim:show-reliability", onShow);
    return () => window.removeEventListener("lithrim:show-reliability", onShow);
  }, [agent]);
  // SWEEP (RIGOR-1 / Q1 — NEW-G3): the "Reliability sweep" trigger — fetch the REAL sweep endpoint
  // (GET /v1/reliability/{agent}/sweep, $0 read) and render the tool-sweep_card INLINE as a fresh
  // assistant turn (the same window-bridge idiom as show-reliability; conversational-first, no new
  // tab, NO 25th agent tool). detail.k_max / detail.role scope the sweep when set. The endpoint
  // returns {agent, sweep, n_cases}; the card reads the flat-spread `sweep`. On error/404/no samples
  // the card's honest empty state shows ("No sampled runs yet"); NEVER a fabricated curve.
  useEffect(() => {
    const onSweep = async (e) => {
      let output = {};
      try {
        const r = await getReliabilitySweep(agent, { k_max: e?.detail?.k_max, role: e?.detail?.role });
        output = { ...(r?.sweep || {}) };
      } catch { output = {}; }
      setChat((c) => [
        ...c,
        { role: "assistant", text: "", parts: [{ type: "tool-sweep_card", state: "output-available", output }] },
      ]);
    };
    window.addEventListener("lithrim:show-sweep", onSweep);
    return () => window.removeEventListener("lithrim:show-sweep", onSweep);
  }, [agent]);
  const taRef = useRef(null);
  const fileRef = useRef(null); // CE-INGEST-FRONTDOOR-1: the hidden upload input (the only chrome)
  const [uploading, setUploading] = useState(false);
  const convoRef = useRef(null); // the scroll container
  const bottomRef = useRef(null); // autoscroll anchor at the end of the thread
  const [atBottom, setAtBottom] = useState(true); // is the user reading the latest turn?
  const [showExample, setShowExample] = useState(false); // S-BS-89: the scripted showcase is opt-in

  const send = async () => {
    const message = input.trim();
    if (!message || sending) return;
    // ONB-0 (S-BS-87): snapshot the PRIOR turns as history BEFORE the optimistic append
    // (so the just-added empty assistant placeholder is naturally excluded). Text-only —
    // map `text`->`content`, drop `parts`; the loop replays this as context.
    const history = chat.map((m) => ({ role: m.role, content: m.text || "" }));
    setInput("");
    setSending(true);
    setChat((c) => [...c, { role: "user", text: message }, { role: "assistant", text: "", parts: [] }]);
    const patchLast = (fn) =>
      setChat((c) => {
        const next = c.slice();
        next[next.length - 1] = fn(next[next.length - 1]);
        return next;
      });
    try {
      const { chatStream } = await import("./bff.js");
      await chatStream(
        { message, agent, history, active_case: activeCase },
        {
          onEvent: (ev) => {
            if (ev.event === "assistant_delta") patchLast((m) => ({ ...m, text: (m.text || "") + ev.text }));
            else if (ev.event === "thinking")
              // CONV-UX-1 (W1/W2): the model's reasoning stream — accreted into a collapsible
              // muted section. Only present when the SDK surfaces a ThinkingBlock/thinking_delta.
              patchLast((m) => ({ ...m, thinking: (m.thinking || "") + ev.text }));
            else if (ev.event === "tool_call") {
              // CONV-UX-1 (W1): an ordered activity step. Mark any prior running step done (the
              // SDK emits the next tool_call only after the previous tool resolved), then append
              // the new running step so the indicator shows the latest in-flight label.
              patchLast((m) => {
                const activity = (m.activity || []).map((s) => ({ ...s, state: "done" }));
                activity.push({ name: ev.name, label: toolLabel(ev.name), state: "running" });
                return { ...m, activity };
              });
            } else if (ev.event === "tool_result" && ev.part) {
              // W1: a result drained — the latest running step is done.
              patchLast((m) => ({
                ...m,
                activity: (m.activity || []).map((s) => ({ ...s, state: "done" })),
              }));
              // CHATBIND-2: a tool-open_artifact part is a pane-control DIRECTIVE, not a card.
              // Fire the open+focus side-effect ON ARRIVAL (once); it still appends so the turn
              // shows a tiny affordance (special-cased OUT of renderTool in the render map below).
              if (ev.part.type === "tool-open_artifact") {
                const t = ev.part.output?.tab;
                if (ARTIFACT_TABS.includes(t)) onOpenArtifact?.(t);
              }
              // CHATBIND-4: a tool-propose_live_run DIRECTIVE opens the in-DOM CostModal — the agent
              // PROPOSES; only the human's confirm (confirmPaidRun) spends. The agent never runs paid.
              // CHAT-CASE-TARGET-1: the directive carries the case the chat NAMED — sync the UI to it
              // (mirrors the show_case lift @387) AND carry it so confirmPaidRun grades THAT case, not
              // the stale top-bar selection. case_id is a selector; the human's confirm is still the
              // sole spend. Empty output -> caseId undefined -> the TopBar fallback path is unchanged.
              if (ev.part.type === "tool-propose_live_run") {
                const cid = ev.part.output?.case_id || null;
                if (cid) onActiveCase?.(cid);
                setPaid({ open: true, busy: false, caseId: cid });
              }
              // RUN-ALL-1: a tool-propose_run_all DIRECTIVE opens the SAME in-DOM CostModal in COHORT
              // mode — the agent PROPOSES; only the human's confirm (confirmPaidRun) grades all cases.
              if (ev.part.type === "tool-propose_run_all") setPaid({ open: true, busy: false, cohort: true });
              // NARR-CHAT-LOOP: a show_case card carries the case_id it opened — lift it into the
              // shared active case so the chat↔UI stay ONE thing (the Case pane + a later Run target
              // the case the chat just opened). The agent can never open a case it didn't pass.
              if (ev.part.type === "tool-case_summary" && ev.part.output?.case_id)
                onActiveCase?.(ev.part.output.case_id);
              patchLast((m) => ({ ...m, parts: [...(m.parts || []), ev.part] }));
            } else if (ev.event === "run_result")
              // CHATBIND-2 (D4): lift the chat's $0 replay into the shell's shared runResult so
              // the focused Report/Judge tab shows THIS run (byte-same to the manual Run-eval).
              onRunResult?.(ev.result);
            else if (ev.event === "error")
              // W1/W3: a loop error closes the activity (no step left spinning) and flags the
              // turn errored so the render guard suppresses any card from the failed turn.
              patchLast((m) => ({
                ...m,
                errored: true,
                activity: (m.activity || []).map((s) => ({ ...s, state: "done" })),
                text: (m.text ? m.text + "\n\n" : "") + `⚠ ${friendlyError(ev.detail)}`,
              }));
          },
        },
      );
    } catch (err) {
      patchLast((m) => ({ ...m, text: (m.text ? m.text + "\n\n" : "") + `⚠ ${friendlyError(err)}` }));
    } finally {
      setSending(false);
    }
  };

  const onComposerKey = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      send();
    }
  };

  // D2 cadence — autoscroll to the latest turn as it streams, but only when the user is
  // already near the bottom; if they've scrolled up to read, leave them be and surface a
  // "↓ latest" affordance instead (D-F).
  useEffect(() => {
    if (atBottom) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [chat, atBottom]);

  // PERSIST-CONV: HYDRATE the stored thread on mount / agent-change so a refresh restores the
  // conversation. Don't clobber an in-progress send (guard on !sending); a brand-new agent has no
  // stored thread → [] (correct empty-state). `hydratedRef` gates the persist effect below.
  //
  // Reset the displayed thread SYNCHRONOUSLY before fetching: the no-clobber guard below applies
  // the new thread only onto a still-empty chat, so without this an `agent` change WITHOUT a
  // remount (the active-agent auto-resolution flip, or any future swap that doesn't bump the
  // sessionKey) would leave the OLD agent's thread on screen under the NEW agent — one
  // evaluation's conversation bleeding into another (a conversational-first correctness/trust
  // bug). The in-flight-send guard still holds: a send that lands AFTER this reset makes `chat`
  // non-empty, and `c.length === 0 ? thread : c` then keeps the user's just-sent turn.
  useEffect(() => {
    let live = true;
    hydratedRef.current = null;
    setChat([]);
    (async () => {
      let thread = [];
      try {
        const res = await getConversation(agent);
        if (Array.isArray(res?.thread)) thread = res.thread;
      } catch {
        /* offline / first paint → the clean empty-state, never a crash */
      }
      if (!live) return;
      // Never clobber a turn already in flight: apply the hydrated thread only onto a still-empty
      // chat (a send that landed first wins; the persist effect then keeps the store current).
      if (thread.length) setChat((c) => (c.length === 0 ? thread : c));
      hydratedRef.current = agent;
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent, reloadTick]);

  // PERSIST-CONV: PERSIST the settled thread (debounced) once a turn finishes — not while
  // `sending` (only the final thread persists), only after the hydrate landed for THIS agent
  // (so an empty hydrate never overwrites a stored thread), and only when non-empty (a brand-new
  // agent with no turn writes nothing — no clobber of nothing).
  useEffect(() => {
    if (sending || hydratedRef.current !== agent || chat.length === 0) return;
    const t = setTimeout(() => {
      putConversation(agent, chat).catch(() => {
        /* best-effort — a failed persist must never break the live turn */
      });
    }, 400);
    return () => clearTimeout(t);
  }, [chat, sending, agent]);

  // PERSIST-CONV: the "clear conversation" affordance — reset the thread to the empty-state AND
  // clear the durable store (so the cleared thread survives a refresh too). The now-empty chat
  // writes nothing back (the persist effect early-returns on length 0); `hydratedRef` stays this
  // agent so a later turn persists straight away. Best-effort delete — the UI is already reset.
  const clearChat = async () => {
    setClearing(false);
    setChat([]);
    hydratedRef.current = agent;
    try {
      await deleteConversation(agent);
    } catch {
      /* the store self-heals on the next turn's persist; never block the reset on a failed delete */
    }
  };

  const onConvoScroll = () => {
    const el = convoRef.current;
    if (!el) return;
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  };

  const jumpToLatest = () => {
    setAtBottom(true);
    bottomRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  };

  // D2 cadence — grow the composer with multi-line input (capped ~5 rows / 200px); since
  // send() clears `input`, this also shrinks it back to one row after a turn.
  useLayoutEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [input]);

  // S-BS-89: empty-state suggestions FILL the composer (never auto-send — intent stays the
  // user's, as does the eventual spend on a paid run).
  const fillPrompt = (text) => {
    setInput(text);
    taRef.current?.focus();
  };

  // CE-INGEST-FRONTDOOR-1: the upload front door. Read the file, POST /preview (decode + a JUTE
  // template + apply — pins NOTHING), and inject an IngestPreviewCard for the human to validate
  // before /commit. Deterministic + cheap; the file picker is the only chrome, the rest is inline.
  const onUploadFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setChat((c) => [...c, { role: "user", text: `📎 ${file.name}`, parts: [] }]);
    const card = (output) => setChat((c) => [...c, {
      role: "assistant", text: "", parts: [{ type: "tool-ingest_preview", state: "output-available", output }],
    }]);
    let raw;
    try { raw = await file.text(); }
    catch (err) {
      setChat((c) => [...c, { role: "assistant", text: `⚠ ${friendlyError(err)}`, parts: [] }]);
      setUploading(false); if (fileRef.current) fileRef.current.value = ""; return;
    }
    try {
      const res = await ingestPreview({ raw, fmt: "auto", filename: file.name, agent });
      card({ ...res, raw, filename: file.name, agent });
    } catch (err) {
      // failure-recovery: render the card in an error state (rules box + retry), NOT a dead-end line
      card({ error: friendlyError(err), raw, filename: file.name, agent });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = ""; // allow re-selecting the same file
    }
  };

  // The PAID path the agent can NOT take: a human-confirmed in-process run, gated by the in-DOM
  // CostModal (never window.confirm). CHAT-FRESH-GRADE-1: confirming GRADES THE CASE FRESH — one
  // cost-gated in_process grade (the SAME paid path the TopBar "Run live" button takes) — then
  // (a) appends the fresh verdict card to the chat thread (so the conversation shows the fresh
  // result, not a stale replay) and (b) lifts the SAME rec to the report via onRunResult. It runs
  // the grade ITSELF (not onRunEval) so it gets the rec back without editing app.jsx, and it never
  // ALSO calls onRunEval — a single paid call, no double-spend. The TopBar "Run live" path is
  // unchanged (it still calls onRunEval directly).
  const confirmPaidRun = async () => {
    setPaid((p) => ({ ...p, busy: true }));
    try {
      // RUN-ALL-1: the COHORT path — grade ALL ingested cases (one cost-confirmed batch) and render
      // the consolidated scorecard INLINE in the chat (the same registry card the agent would emit).
      if (paid.cohort) {
        // COHORT-SUBSET-1: paid.caseIds (from "Run selected") scopes the grade to the checked subset;
        // null (from "Grade all" / propose_run_all) grades EVERY ingested case. The scorecard the
        // ScorecardCard renders is scoped to whatever gradeCases returns for that request.
        const resp = await gradeCases({ agent, in_process: true, ...(paid.caseIds ? { case_ids: paid.caseIds } : {}) });
        const output = { ...(resp.scorecard || {}), grade_path: resp.summary?.grade_path };
        setChat((c) => [
          ...c,
          { role: "assistant", text: "", parts: [{ type: "tool-scorecard", state: "output-available", output }] },
        ]);
        setPaid({ open: false, busy: false });
        return;
      }
      // CHAT-CASE-TARGET-1: grade the case the directive carried (the chat-named case), falling back
      // to the client active case for the TopBar "Run live" path (no directive -> no paid.caseId).
      const target = paid.caseId || activeCase;
      const rec = await runEval({ agent, in_process: true, confirm: true, ...(target ? { case_id: target } : {}) });
      // (a) the fresh result renders as a verdict card INLINE in the chat (the same card the agent
      // emits) — appended as a fresh assistant turn so it survives + persists with the thread.
      setChat((c) => [
        ...c,
        { role: "assistant", text: "", parts: [{ type: "tool-verdict_card", state: "output-available", output: verdictShape(rec) }] },
      ]);
      // (b) lift the SAME rec to the shared report (Report/Judge tabs + run history) — consistent.
      onRunResult?.(rec);
    } catch (err) {
      setChat((c) => [...c, { role: "assistant", text: `⚠ ${friendlyError(err)}`, parts: [] }]);
    } finally {
      setPaid({ open: false, busy: false });
    }
  };

  return (
    <main className="center">
      <div className="center-hd">
        <div style={{ minWidth: 0 }}>
          <div className="h-title">{showExample ? "Example conversation" : agentLabel(agent)}</div>
        </div>
        {showExample && (
          <>
            <span className="chip"><span className="d" style={{ background: "var(--accent)" }} /> Run in progress</span>
            <span className="chip">sample case</span>
          </>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          {/* ACTIVE-CASE-1: the active case is ALWAYS visible — "this case" never resolves to a
              hidden default. Null = nothing auto-picked; the user names a case in the chat or picks
              one via Explore case (the agent's None-branch then lists the corpus + asks). */}
          {!showExample && (
            <span
              className="chip"
              title={activeCase ? `Active case: ${activeCase}` : "No case selected — name a case in the chat, or pick one via Explore case"}
              style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
            >
              {activeCase ? `Case: ${activeCase}` : "No case selected"}
            </span>
          )}
          {showExample && (
            <button className="btn btn-ghost" title="Hide the example conversation" onClick={() => setShowExample(false)}>
              <Icon name="close" size={14} /> Hide example
            </button>
          )}
          {/* PERSIST-CONV: clear this conversation (durable store + on-screen thread). Only when
              there's a settled thread to clear; an in-DOM two-step confirm (never window.confirm —
              it freezes the renderer to CDP), since a cleared thread does not come back. */}
          {!showExample && chat.length > 0 && !sending && (
            clearing ? (
              <span className="chip" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                Clear conversation?
                <button className="btn btn-ghost" data-testid="chat-clear-confirm" onClick={clearChat}>Clear</button>
                <button className="btn btn-ghost" onClick={() => setClearing(false)}>Cancel</button>
              </span>
            ) : (
              <button className="btn btn-ghost" title="Clear conversation" aria-label="Clear conversation" onClick={() => setClearing(true)}>
                <Icon name="close" size={14} /> Clear
              </button>
            )
          )}
          {/* REFRESH-1: was a dead button — now re-pulls the durable thread (a no-op mid-send:
              the in-flight turn owns the screen until it settles). */}
          <button className="icon-btn" title="Reload this conversation" aria-label="Reload this conversation"
            onClick={() => { if (!sending) setReloadTick((t) => t + 1); }}>
            <Icon name="refresh" size={16} />
          </button>
          {!artifactOpen && (
            <>
              {/* FINDING #2 (UI-pass 2026-07-04): with no case selected, "Explore case" opens the
                  Cases BROWSER (pick explicitly) — never the default-case view under a "No case
                  selected" header. With a selection it jumps straight to that case. */}
              <button className="btn btn-ghost" onClick={() => onOpenArtifact(activeCase ? "case" : "corpus")}>
                <Icon name="search" size={15} /> Explore case
              </button>
              <button className="btn btn-ghost" onClick={() => onOpenArtifact("report")}>
                <Icon name="panel" size={15} /> Open report
              </button>
            </>
          )}
        </div>
      </div>

      <div className="convo" ref={convoRef} onScroll={onConvoScroll}>
        <div className="convo-inner">

          {/* S-BS-89: the scripted 8-message showcase is now OPT-IN (showExample). The clean
              empty-state below is the real default surface; the frozen Journey stays the
              canonical demo (root.jsx mode="journey"), untouched. */}
          {showExample && (
            <>
          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">assistant</span></div>
              <p>Welcome back. We're configuring an evaluation for <strong>your agent</strong>. Let's confirm the domain, then kick off a run.</p>
              <ConfigCard onOpen={() => onOpenArtifact("config")} />
            </div>
          </div>

          <div className="msg user">
            <div className="av user">L</div>
            <div className="content">
              <div className="name">You</div>
              <p>Looks right. Bump it to the full sample set and keep the safety checks on — let's see where the agent slips.</p>
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">assistant</span></div>
              <p>Before the full run, let's finish the setup. Choose what to flag and how serious each issue is, add a fact-check, and connect a reference knowledge base — each choice is saved to this evaluation.</p>
              {/* EVAL-FLOW (W1b): thread the ACTIVE agent into the ContractBuilder card so its
                  self-persist (POST /v1/grounding-contract → the audited write) lands on the
                  agent the rail derives from → captureSetup → refreshJourney ticks Ground truth. */}
              {SETUP_PARTS.map(([type, key]) => (
                <div key={key}>
                  {renderTool({ type, state: "output-available", output: { agent } }, { onResult: captureSetup(key) })}
                </div>
              ))}
              <p style={{ fontSize: 12.5, color: "var(--muted)" }}>
                Saved so far: <strong>{captured.length ? captured.join(" · ") : "nothing yet"}</strong>
              </p>
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">assistant</span></div>
              <p>Set up the evaluation — its judges, the things they check for, and any tools they use. Every change is saved and logged, so you can always see who changed what, when, and why.</p>
              {renderTool({ type: "tool-agent_editor", state: "output-available" }, { onResult: captureSetup("agent") })}
              {renderTool({ type: "tool-audit_log", state: "output-available" })}
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">assistant</span></div>
              <p>Now author a <strong>judge</strong>. Assign an ontology flag lens to a role — the prompt preview updates live and <code className="inl">$0</code> (no model call), showing the exact <code className="inl">role_key_questions</code> the bridge will send. The live verdict-change is the paid finale, in a run.</p>
              {/* S-BS-153: target the ACTIVE agent so the save's roster-add lands on the agent
                  the rail derives from → refreshJourney (via captureSetup) flips Judges done. */}
              {renderTool({ type: "tool-judge_editor", state: "output-available", output: { role: "risk_judge", agent } }, { onResult: captureSetup("judge") })}
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">assistant</span></div>
              <p>Everything checks out. Running the full set takes a few minutes; I'll stream verdicts into the report as they land.</p>
              {/* EVAL-FLOW (W3): thread the active agent + an onRan callback so the card's run
                  lifts the result into the shared report AND re-derives the rail (Run ticks). */}
              {renderTool({ type: "tool-run_panel", state: "output-available", output: { agent, onRan: (rec) => { onRunResult?.(rec); onConfigSaved?.(); } } })}
              <div className="msg-actions">
                <button className="btn btn-primary" disabled={runStatus === "loading"}
                  onClick={() => onRunEval(false)}>
                  <Icon name="bolt" size={14} /> {runStatus === "loading" ? "Running…" : "Run evaluation"}
                </button>
                <button className="btn btn-ghost" onClick={() => onOpenArtifact("report")}>
                  <Icon name="panel" size={14} /> Open report
                </button>
              </div>
            </div>
          </div>
            </>
          )}

          {/* S-BS-89 + SHEPHERD-1 (W4): the clean default surface is now shepherd-aware. The
              primary "Start guided setup" kicks off the agent-led journey; a secondary chip
              offers the NEXT incomplete step (from the live-derived plan, App-side). Both FILL
              the composer (no auto-send — intent + the eventual spend stay the human's). */}
          {chat.length === 0 && !showExample && (
            <div className="empty-state">
              <div className="es-mark"><Mark size={30} /></div>
              <h2 className="es-title">What do you want to evaluate?</h2>
              <p className="es-sub">
                Set up an evaluation by chatting with the assistant, or pick a starting point
                below. You can explore a test case, run an evaluation to get a verdict, and open
                the report — every change is tracked with a full audit trail.
              </p>
              {!chatReady && (
                <div data-testid="connect-assistant-cta" className="reveal"
                  style={{ margin: "0 auto 12px", maxWidth: 460, padding: "10px 14px", borderRadius: 10,
                    border: "1px solid var(--border)", background: "var(--panel)", fontSize: 13, lineHeight: 1.5 }}>
                  The assistant isn't connected yet — chat needs a model.
                  <button className="es-prompt" style={{ marginLeft: 10 }}
                    onClick={() => window.dispatchEvent(new CustomEvent("lithrim:connect-ai"))}>
                    <Icon name="spark" size={14} /> Connect AI
                  </button>
                </div>
              )}
              <div className="es-prompts">
                <button className="es-prompt" data-testid="start-guided-setup"
                  onClick={() => fillPrompt(GUIDED_SETUP_PROMPT)}>
                  <Icon name="spark" size={14} /> Start guided setup
                </button>
                {nextStepName && STEP_PROMPTS[nextStepName] && (
                  <button className="es-prompt" data-testid="next-step-prompt"
                    onClick={() => fillPrompt(STEP_PROMPTS[nextStepName])}>
                    <Icon name="spark" size={14} /> Next: {nextStepName}
                  </button>
                )}
              </div>
              <button className="es-example" onClick={() => setShowExample(true)}>
                Show example conversation
              </button>
            </div>
          )}

          {/* READINESS (conversational-first): when the pinned pack declares a fact-check this agent
              can't run, surface the gaps INLINE — before the first run — with a one-click fix that
              fills the composer with the remediation. Never a static pane; bound to the REAL BFF
              readiness report. Hidden when ready (ok) so a healthy setup shows nothing. */}
          {chat.length === 0 && !showExample && readiness && readiness.ok === false && (
            <div className="reveal" style={{ margin: "0 auto 8px", maxWidth: 640, width: "100%" }} data-testid="readiness-gaps">
              {renderTool(
                { type: "tool-readiness_card", state: "output-available", output: readiness },
                { onFix: (f) => fillPrompt(f.remediation || `Add the fact-check for ${f.code}`) },
              )}
            </div>
          )}

          {/* UAP-5b / R11: the LIVE conversational loop. Streamed assistant turns +
              tool-result gen-UI parts (rendered via the existing registry). */}
          {chat.map((m, i) =>
            m.role === "user" ? (
              <div className="msg user" key={i}>
                <div className="av user">You</div>
                <div className="content">
                  <div className="name">You</div>
                  <p style={{ whiteSpace: "pre-wrap" }}>{m.text}</p>
                </div>
              </div>
            ) : (
              (() => {
                const isLast = i === chat.length - 1;
                const inFlight = sending && isLast; // this turn is still streaming
                // W3: dedup cards by type within this turn (one card per type), the seen-set the
                // monitor specified; directives are NOT deduped (they are per-call pane traces).
                const seen = new Set();
                // W1: the latest in-flight tool label drives the working indicator (a running step,
                // else a generic "Thinking…"); shown across the WHOLE in-flight window.
                const running = (m.activity || []).find((s) => s.state === "running");
                const indicatorLabel = running ? running.label : "Thinking…";
                return (
                  <div className="msg" key={i}>
                    <div className="av ai"><Mark size={17} /></div>
                    <div className="content">
                      <div className="name">Lithrim</div>
                      {/* W1: the model's reasoning, collapsible + muted (only when streamed). */}
                      {m.thinking && (
                        <details className="reasoning">
                          <summary>Reasoning</summary>
                          <div className="reasoning-bd">{m.thinking}</div>
                        </details>
                      )}
                      {/* W1: the ordered activity timeline — a step per tool, running→done. */}
                      {(m.activity || []).length > 0 && (
                        <div className="activity" data-testid="activity">
                          {m.activity.map((s, k) => (
                            <div key={k} className={"act-step " + s.state}>
                              <span className="act-dot" />
                              <span className="act-lbl">{s.label}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* W2: soft block reveal — `reveal` fades each settled block in, no hard snap. */}
                      {m.text && <div className="reveal"><Markdown>{m.text}</Markdown></div>}
                      {/* W3: error-guard — a turn that errored renders NO card (an off-context card
                          must never sit next to an error). */}
                      {!m.errored && (m.parts || []).map((part, j) => {
                        // CHATBIND-2/4: pane-control + cost-confirm DIRECTIVES render as tiny non-card
                        // traces, NEVER through renderTool + never deduped (per-call pane traces).
                        if (part.type === "tool-open_artifact")
                          return (
                            <div key={j} data-testid="pane-directive" style={{ color: "var(--muted)", fontSize: 12.5, margin: "2px 0" }}>
                              ↗ Opened the {TAB_LABELS[part.output?.tab] || "artifact"} panel
                            </div>
                          );
                        if (part.type === "tool-propose_live_run")
                          return (
                            <div key={j} data-testid="paid-directive" style={{ color: "var(--muted)", fontSize: 12.5, margin: "2px 0" }}>
                              ↗ Surfaced the cost-confirm — you authorize the paid run
                            </div>
                          );
                        // RUN-ALL-1: the cohort twin of the same directive — a trace, never a card
                        // (it previously fell through to the "Unsupported component" fallback).
                        if (part.type === "tool-propose_run_all")
                          return (
                            <div key={j} data-testid="paid-directive" style={{ color: "var(--muted)", fontSize: 12.5, margin: "2px 0" }}>
                              ↗ Surfaced the cost-confirm — you authorize grading the full cohort
                            </div>
                          );
                        // W3: dedup — render at most one card per type this turn.
                        if (seen.has(part.type)) return null;
                        seen.add(part.type);
                        // W3: an `ondemand` part (a passive orientation read, e.g. the audit trail)
                        // collapses to a compact "Show … ▸" affordance — a full card only on click,
                        // so the agent's footing-finding reads don't throw cards off-context.
                        if (part.show_intent === "ondemand")
                          return (
                            <details key={j} className="ondemand" data-testid="ondemand-part">
                              <summary>Show {PART_LABELS[part.type] || "details"} ▸</summary>
                              <div className="reveal">{renderTool(part, { onResult: captureSetup(`chat-${i}-${j}`), onOpenArtifact, onOpenCaseRun })}</div>
                            </details>
                          );
                        // CHATBIND-3: pass onOpenArtifact so a CaseCard's "View case ->" opens the Case tab.
                        return <div key={j} className="reveal">{renderTool(part, { onResult: captureSetup(`chat-${i}-${j}`), onOpenArtifact, onOpenCaseRun })}</div>;
                      })}
                      {/* W1/W2: the non-static working indicator — visible across the WHOLE in-flight
                          window (not only when text is empty), showing the latest tool label. */}
                      {inFlight && (
                        <div className="working" data-testid="working-indicator">
                          <span className="working-dots"><i /><i /><i /></span>
                          <span className="working-lbl">{indicatorLabel}</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })()
            ),
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {!atBottom && chat.length > 0 && (
        <button className="jump-latest" onClick={jumpToLatest} title="Jump to latest">
          <Icon name="chevD" size={15} /> Latest
        </button>
      )}

      <CostModal
        open={paid.open}
        busy={paid.busy}
        title={paid.cohort
          // COHORT-SUBSET-1 last-mile: a non-empty paid.caseIds means the user picked a SUBSET
          // ("Run selected (N)") — the copy must name the N-case subset, not "all cases". An
          // absent/empty caseIds ("Grade all" / propose_run_all) keeps the whole-cohort copy.
          ? (paid.caseIds?.length
            ? `Grade ${paid.caseIds.length} selected case${paid.caseIds.length === 1 ? "" : "s"} (paid)?`
            : "Grade all cases (paid)?")
          : "Run a live, paid evaluation?"}
        body={paid.cohort
          ? (paid.caseIds?.length
            ? `This grades the ${paid.caseIds.length} selected case${paid.caseIds.length === 1 ? "" : "s"} in one paid batch (model calls you'll be billed for) and shows a consolidated scorecard. The assistant can't do this — only you can authorize it.`
            : "This grades every ingested case in one paid batch (model calls you'll be billed for) and shows a consolidated scorecard. The assistant can't do this — only you can authorize it.")
          : "This runs one real, paid evaluation (model calls you'll be billed for). The assistant can't do this — only you can authorize it."}
        confirmLabel={paid.cohort
          ? (paid.caseIds?.length
            ? `Grade ${paid.caseIds.length} selected case${paid.caseIds.length === 1 ? "" : "s"} (paid)`
            : "Grade all cases (paid)")
          : "Run live (paid)"}
        warning={readiness && readiness.ok === false
          ? `Setup readiness: this agent has a fact-check that won't run for the ${readiness.pack || "pinned"} pack — a false alarm could go uncaught. Fix it first, or run anyway.`
          : null}
        onConfirm={confirmPaidRun}
        onCancel={() => setPaid({ open: false, busy: false })}
      />

      <div className="composer">
        <div className="composer-inner">
          <div className="composer-box">
            <textarea
              ref={taRef}
              rows="1"
              placeholder="Ask Lithrim to explore a case, run an evaluation, or open the report…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onComposerKey}
              disabled={sending}
            />
            <div className="composer-bar">
              <div className="left">
                <button className="icon-btn" title="Run a live, paid evaluation (you authorize the spend)"
                  onClick={() => setPaid({ open: true, busy: false })}>
                  <Icon name="bolt" size={16} />
                </button>
                {/* CE-INGEST-FRONTDOOR-1: load eval cases from a JSON / JSONL / CSV file. The picker
                    is the only chrome; preview → approve renders inline as gen-UI. */}
                <button className="icon-btn" data-testid="upload-cases"
                  title="Load eval cases from a JSON, JSONL, or CSV file"
                  disabled={uploading || sending} onClick={() => fileRef.current?.click()}>
                  <Icon name={uploading ? "refresh" : "attach"} size={16} />
                </button>
                <input ref={fileRef} type="file" accept=".json,.jsonl,.ndjson,.csv,application/json,text/csv"
                  style={{ display: "none" }} data-testid="upload-input"
                  onChange={(e) => onUploadFile(e.target.files?.[0])} />
              </div>
              <span className="kbd" style={{ marginLeft: 4 }}>⌘↵ to send</span>
              <div className="send">
                <button className="send-btn" data-testid="chat-send" disabled={sending || !input.trim()} onClick={send}>
                  <Icon name="send" size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
