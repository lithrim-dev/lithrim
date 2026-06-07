/* panes.jsx — left rail, center conversation (ported verbatim; placeholder mark → real logo). */
import { useRef, useState, useEffect, useLayoutEffect } from "react";
import { Icon } from "./icons.jsx";
import { Mark, Wordmark } from "./brand.jsx";
import { ConfigCard } from "./cards.jsx";
import { renderTool } from "./genui/index.js";
import { CostModal } from "./components/CostModal.jsx";
import { Markdown } from "./components/Markdown.jsx";
import { THREADS, STEPS } from "./data.jsx";

// S-BS-19: the scripted host emits INPUT tool-parts; each widget's onResult threads
// the collected config into local config-plane state (the §3 "the conversation writes
// the config plane" loop). Local state per decision #3 (Zustand deferred).
const SETUP_PARTS = [
  ["tool-flag_editor", "flags"],
  ["tool-contract_builder", "contract"],
  ["tool-kb_picker", "kb"],
];

/* ============================ LEFT RAIL ============================ */
export function LeftRail({ width, active, setActive }) {
  return (
    <aside className="rail" style={{ width }}>
      <div className="rail-brand" style={{ display: "flex", alignItems: "center", height: 46, padding: "0 16px", borderBottom: "1px solid var(--border)", flex: "0 0 auto" }}>
        <Wordmark markSize={18} />
      </div>
      <div className="rail-sec">
        <div className="rail-hd">
          <span className="lbl">Evaluations</span>
          <button className="icon-btn" title="New evaluation"><Icon name="plus" size={16} /></button>
        </div>
        <div className="tb-cmd" style={{ position: "static", transform: "none", width: "100%", height: 32 }}>
          <Icon name="search" size={14} /><span>Search</span><span className="kbd">⌘K</span>
        </div>
      </div>
      <div className="rail-scroll">
        <div style={{ padding: "8px 12px 0" }}>
          {THREADS.map((t) => (
            <div key={t.id} className={"thread" + (active === t.id ? " active" : "")} onClick={() => setActive(t.id)}>
              <span className="st" style={{ background: t.color }} />
              <div className="tt">
                <div className="ti">{t.title}</div>
                <div className="ts">{t.sub}</div>
              </div>
              <div className="tm">{t.meta}</div>
            </div>
          ))}
        </div>
        <div className="journey">
          <div className="rail-hd" style={{ padding: "12px 6px 12px" }}>
            <span className="lbl">Setup journey</span>
            <span className="tm" style={{ fontFamily: "var(--mono)" }}>4 / 6</span>
          </div>
          {STEPS.map((s, i) => (
            <div key={s.name} className={"step " + s.state}>
              <div className="nodecol">
                <div className="node">{s.state === "done" ? <Icon name="check" size={12} sw={2.4} /> : i + 1}</div>
                {i < STEPS.length - 1 && <div className="line" />}
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
        <div className="avatar">JR</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="who">Jordan Reyes</div>
          <div className="org">acme-health · Pro</div>
        </div>
        <button className="icon-btn"><Icon name="dots" size={16} /></button>
      </div>
    </aside>
  );
}

/* ============================ CENTER ============================ */
export function CenterPane({ onOpenArtifact, artifactOpen, onRunEval, runStatus, agent = "ws0_default" }) {
  // config-plane state the input tool-parts write into (S-BS-19).
  const [setup, setSetup] = useState({});
  const captureSetup = (key) => (result) => setSetup((s) => ({ ...s, [key]: result }));
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
        { message, agent, history },
        {
          onEvent: (ev) => {
            if (ev.event === "assistant_delta") patchLast((m) => ({ ...m, text: (m.text || "") + ev.text }));
            else if (ev.event === "tool_result" && ev.part)
              patchLast((m) => ({ ...m, parts: [...(m.parts || []), ev.part] }));
            else if (ev.event === "error")
              patchLast((m) => ({ ...m, text: (m.text ? m.text + "\n\n" : "") + `⚠ ${ev.detail}` }));
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
          <div className="h-title">Scribe Agent v4</div>
        </div>
        <span className="chip"><span className="d" style={{ background: "var(--accent)" }} /> Run in progress</span>
        <span className="chip">2,400 samples</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button className="icon-btn" title="Refresh"><Icon name="refresh" size={16} /></button>
          {!artifactOpen && (
            <button className="btn btn-ghost" onClick={() => onOpenArtifact("report")}>
              <Icon name="panel" size={15} /> Open report
            </button>
          )}
        </div>
      </div>

      <div className="convo" ref={convoRef} onScroll={onConvoScroll}>
        <div className="convo-inner">

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Welcome back. We're configuring an evaluation for <strong>Scribe Agent v4</strong>. Four of six steps are done — let's confirm the domain, then kick off the full run.</p>
              <ConfigCard onOpen={() => onOpenArtifact("config")} />
            </div>
          </div>

          <div className="msg user">
            <div className="av user">JR</div>
            <div className="content">
              <div className="name">Jordan</div>
              <p>Looks right. Bump it to the full <code className="inl">2,400</code> samples and keep the safety checks on — fabricated allergies are the one we keep failing.</p>
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Done. Your <strong>judge council</strong> is three models cross-checking every verdict, with a weighted vote and a 0.66 agreement floor. Here's a sample they just scored on the 50-row dry run:</p>
              {renderTool({ type: "tool-verdict_card", state: "output-available" })}
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Calibration on the dry run is tight — predicted confidence tracks observed accuracy within <strong>±3%</strong>, so the council's scores are trustworthy as a stopping signal.</p>
              {renderTool({ type: "tool-calibration_chart", state: "output-available" })}
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Before the full run, let's lock the config plane. Edit the flags &amp; severity, author a verification contract, and bind the knowledge base — each one writes straight into your eval profile.</p>
              {SETUP_PARTS.map(([type, key]) => (
                <div key={key}>
                  {renderTool({ type, state: "output-available" }, { onResult: captureSetup(key) })}
                </div>
              ))}
              <p style={{ fontSize: 12.5, color: "var(--muted)" }}>
                Config plane captured: <strong>{captured.length ? captured.join(" · ") : "nothing yet"}</strong>
              </p>
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Assemble the <strong>agent</strong> — its judge roster, ontology, and tools write straight to the config plane. Every change is attributed and logged; the audit trail below answers who/when/what/why for each edit and each run.</p>
              {renderTool({ type: "tool-agent_editor", state: "output-available" }, { onResult: captureSetup("agent") })}
              {renderTool({ type: "tool-audit_log", state: "output-available" })}
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Now author a <strong>judge</strong>. Assign an ontology flag lens to a role — the prompt preview updates live and <code className="inl">$0</code> (no model call), showing the exact <code className="inl">role_key_questions</code> the bridge will send. The live verdict-change is the paid finale, in a run.</p>
              {renderTool({ type: "tool-judge_editor", state: "output-available", output: { role: "risk_judge", agent: "ws0_default" } }, { onResult: captureSetup("judge") })}
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Everything checks out. Running all 2,400 will take about <strong>6 minutes</strong>; I'll stream verdicts into the report as they land.</p>
              {renderTool({ type: "tool-run_panel", state: "output-available" })}
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

          {/* UAP-5b / R11: the LIVE conversational loop. Streamed assistant turns +
              tool-result gen-UI parts (rendered via the existing registry). */}
          {chat.map((m, i) =>
            m.role === "user" ? (
              <div className="msg user" key={i}>
                <div className="av user">JR</div>
                <div className="content">
                  <div className="name">Jordan</div>
                  <p style={{ whiteSpace: "pre-wrap" }}>{m.text}</p>
                </div>
              </div>
            ) : (
              <div className="msg" key={i}>
                <div className="av ai"><Mark size={17} /></div>
                <div className="content">
                  <div className="name">Lithrim <span className="t">setup assistant</span></div>
                  {m.text && <Markdown>{m.text}</Markdown>}
                  {(m.parts || []).map((part, j) => (
                    <div key={j}>{renderTool(part, { onResult: captureSetup(`chat-${i}-${j}`) })}</div>
                  ))}
                  {!m.text && !(m.parts || []).length && sending && i === chat.length - 1 && (
                    <p style={{ color: "var(--muted)" }}>Thinking…</p>
                  )}
                </div>
              </div>
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
              placeholder="Ask Lithrim, or describe a change to the eval…"
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
