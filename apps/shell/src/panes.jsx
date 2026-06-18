/* panes.jsx — left rail, center conversation (ported verbatim; placeholder mark → real logo). */
import { useRef, useState, useEffect, useLayoutEffect } from "react";
import { Icon } from "./icons.jsx";
import { Mark, Wordmark } from "./brand.jsx";
import { ConfigCard } from "./cards.jsx";
import { renderTool } from "./genui/index.js";
import { CostModal } from "./components/CostModal.jsx";
import { Markdown } from "./components/Markdown.jsx";
import { STEPS } from "./data.jsx";

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
  return (
    <aside className="rail" style={{ width }}>
      <div className="rail-brand" style={{ display: "flex", alignItems: "center", height: 46, padding: "0 16px", borderBottom: "1px solid var(--border)", flex: "0 0 auto" }}>
        <Wordmark markSize={18} />
      </div>
      <div className="rail-sec">
        <div className="rail-hd">
          <span className="lbl">Evaluations</span>
          <button className="icon-btn" title="New evaluation" aria-label="New evaluation" onClick={onNewEval}><Icon name="plus" size={16} /></button>
        </div>
        <div className="tb-cmd" style={{ position: "static", transform: "none", width: "100%", height: 32 }}>
          <Icon name="search" size={14} /><span>Search</span><span className="kbd">⌘K</span>
        </div>
      </div>
      <div className="rail-scroll">
        <div style={{ padding: "8px 12px 0" }}>
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
                {canDelete && (
                  <button className="icon-btn" title="Delete this evaluation" aria-label={`Delete ${name}`}
                    onClick={(e) => { e.stopPropagation(); onDeleteAgent?.(name); }}>
                    <Icon name="close" size={14} />
                  </button>
                )}
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
                <div className="node">{s.state === "done" ? <Icon name="check" size={12} sw={2.4} /> : i + 1}</div>
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
      <div className="rail-foot">
        <div className="avatar">L</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="who">You</div>
          <div className="org">Local workspace</div>
        </div>
        <button className="icon-btn"><Icon name="dots" size={16} /></button>
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
  assemble_agent: "Editing the agent roster",
  get_judge: "Reading the judge",
  author_judge: "Authoring the judge",
  delete_judge: "Reverting the judge",
  author_flag: "Editing the flag",
  create_flag: "Creating the flag",
  delete_flag: "Deleting the flag",
  add_grounding_contract: "Adding a grounding contract",
  run_eval: "Running a $0 replay",
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

export function CenterPane({ onOpenArtifact, artifactOpen, onRunEval, runStatus, agent = "ws0_default", activeCase = null, onActiveCase, onRunResult, onConfigSaved, nextStepName }) {
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
  const [sending, setSending] = useState(false);
  const [paid, setPaid] = useState({ open: false, busy: false }); // the in-DOM cost gate
  const taRef = useRef(null);
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
              if (ev.part.type === "tool-propose_live_run") setPaid({ open: true, busy: false });
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
                text: (m.text ? m.text + "\n\n" : "") + `⚠ ${ev.detail}`,
              }));
          },
        },
      );
    } catch (err) {
      patchLast((m) => ({ ...m, text: (m.text ? m.text + "\n\n" : "") + `⚠ ${String(err.message || err)}` }));
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

  // The PAID path the agent can NOT take: a human-confirmed in-process run, gated by
  // the in-DOM CostModal (never window.confirm). On confirm, hit the EXISTING
  // confirm-gated endpoint via the app's run handler.
  const confirmPaidRun = async () => {
    setPaid((p) => ({ ...p, busy: true }));
    try {
      await onRunEval?.(true); // the existing live/paid path (TopBar's "Run live")
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
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {showExample && (
            <button className="btn btn-ghost" title="Hide the example conversation" onClick={() => setShowExample(false)}>
              <Icon name="close" size={14} /> Hide example
            </button>
          )}
          <button className="icon-btn" title="Refresh"><Icon name="refresh" size={16} /></button>
          {!artifactOpen && (
            <>
              <button className="btn btn-ghost" onClick={() => onOpenArtifact("case")}>
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
                              <div className="reveal">{renderTool(part, { onResult: captureSetup(`chat-${i}-${j}`), onOpenArtifact })}</div>
                            </details>
                          );
                        // CHATBIND-3: pass onOpenArtifact so a CaseCard's "View case ->" opens the Case tab.
                        return <div key={j} className="reveal">{renderTool(part, { onResult: captureSetup(`chat-${i}-${j}`), onOpenArtifact })}</div>;
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
        title="Run a live, PAID evaluation?"
        body="This fires one real, in-process council run (paid Azure calls). The assistant cannot do this — only you can authorize the spend."
        confirmLabel="Run live (paid)"
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
