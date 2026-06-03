/* jp3.jsx — Phase 3 (HERO): Grounding — the tool-grounded floor overrules the confident judge. */
import { useState } from "react";
import { Icon } from "../icons.jsx";
import { AgentMsg } from "./chrome.jsx";
import { EXCHANGE, PAIR, FLOOR, ALIGN, PROGRESSION, JUTE_RUN, JUTE_PROMPT, BOT_HINTS, CALIB } from "./journeyData.js";

// Lithrim bot's logged commentary for a beat — read from real experiments (BOT_HINTS · docs/research/RUN_*).
function LithrimNotes({ beat }) {
  const hints = BOT_HINTS.filter((h) => h.beat === beat);
  if (!hints.length) return null;
  return (
    <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
      {hints.map((h, i) => (
        <div key={i} className="icard" style={{ padding: "9px 12px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: h.kind === "wrong" ? "var(--accent)" : "var(--teal)", marginBottom: 3 }}>
            Lithrim · {h.kind === "wrong" ? "what went wrong" : "how it improved"}
          </div>
          <div style={{ fontSize: 12.5, lineHeight: 1.5 }}>{h.text}</div>
          <div className="sc-s" style={{ marginTop: 4, opacity: 0.65 }}>logged · {h.src}</div>
        </div>
      ))}
    </div>
  );
}

export function Center3({ calibStep, calibBusy, runCalibStep }) {
  const score = CALIB.scores[calibStep];
  const done = calibStep >= CALIB.levers.length;
  return (
    <div className="convo-inner">
      <AgentMsg beat="Act 3 · Calibration"
        lead="Whatever your agent ships — support replies, code, RAG answers, clinical notes — you trust an LLM to judge it. You just watched that judge be confidently, unanimously wrong. The only way to fix that is to measure it against truth you actually know.">
        <div className="icard" style={{ marginTop: 12, padding: "11px 14px", fontSize: 12.5, lineHeight: 1.5 }}>
          <div className="sc-s" style={{ marginBottom: 3 }}>WHY THE NUMBER IS TRUSTWORTHY</div>
          {CALIB.methodology}
        </div>
        <div className="icard" style={{ marginTop: 12, padding: "12px 16px" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: ".05em" }}>Judge accuracy vs ground truth</span>
            <span style={{ fontSize: 36, fontWeight: 800, lineHeight: 1, color: done ? "var(--teal)" : "var(--accent)" }}>{score}</span>
            <span style={{ fontSize: 12.5, color: "var(--muted)", marginLeft: "auto" }}>target {CALIB.target}</span>
          </div>
          <div style={{ marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
            {CALIB.errors.map((e, i) => {
              const fixed = calibStep >= e.fixedAt;
              return (
                <div key={i} style={{ fontSize: 12.5, padding: "3px 0", display: "flex", gap: 8, color: fixed ? "var(--muted)" : "var(--ink)" }}>
                  <span style={{ color: fixed ? "var(--teal)" : "var(--accent)", fontWeight: 700, flexShrink: 0 }}>{fixed ? "✓" : "✗"}</span>
                  <span style={{ textDecoration: fixed ? "line-through" : "none" }}>{e.text}</span>
                </div>
              );
            })}
            {calibStep === 0 && <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>Confident and unanimous on every one. This is your eval today.</div>}
          </div>
        </div>
      </AgentMsg>

      <AgentMsg lead="So you tune the judge's prompt — right?">
        <p className="muted">{CALIB.promptTrap}</p>
      </AgentMsg>

      {CALIB.levers.slice(0, calibStep).map((lv, i) => (
        <AgentMsg key={i} lead={`✓ You added the ${lv.name}, then re-ran against truth.`}>
          {lv.showBasis && (
            <div className="taxo-chips" style={{ marginBottom: 8 }}>
              {EXCHANGE.flaggedReal.map((c) => (
                <span className="taxo-chip" key={c} style={{ borderColor: "var(--teal)", color: "var(--teal)" }}>
                  <Icon name="check" size={11} sw={2.6} /> {c}
                </span>
              ))}
            </div>
          )}
          <p className="muted">Accuracy vs truth <b style={{ color: "var(--teal)" }}>{lv.from} → {lv.to}</b> — fixed {lv.fixed}{lv.showBasis ? "; every flagged “fabrication” is on file in the chart, which the judge never read" : ""}.</p>
        </AgentMsg>
      ))}

      {!done && (
        <AgentMsg lead={calibStep === 0 ? "No — you don't reword it. You ground it." : "Keep going — one miss left."}>
          <p className="muted">{CALIB.levers[calibStep].why} It runs after the judges, reads a source they couldn't, and doesn't drift with wording. Add it, re-run against truth.</p>
          <div className="verify-cta">
            <button className="btn btn-primary btn-lg" onClick={runCalibStep} disabled={calibBusy}>
              {calibBusy ? <><span className="vs-ring" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} /> Re-running vs truth…</>
                : <><Icon name="shield" size={15} /> Add the {CALIB.levers[calibStep].name} · re-run</>}
            </button>
            <span className="hint">your lever · deterministic · $0</span>
          </div>
        </AgentMsg>
      )}

      {done && (
        <AgentMsg lead="6 / 6 — your judge now matches ground truth.">
          <p className="muted">Measured against known truth: the judge was wrong, prompts couldn't fix it, a deterministic floor could — and you can prove every step. That's the only rigorous way to trust what your agent ships. The example is a clinical scribe; the method is <b>your agent, your eval</b>. Now point it at yours. <b>→</b></p>
          <LithrimNotes beat="calibration" />
        </AgentMsg>
      )}
    </div>
  );
}

export function Artifact3({ calibStep }) {
  const [sub, setSub] = useState("pair");
  const done = calibStep >= 2;
  return (
    <div>
      <div className="art-tabs" style={{ marginBottom: 16 }}>
        <button className={"art-tab" + (sub === "pair" ? " on" : "")} onClick={() => setSub("pair")}>The pair</button>
        <button className={"art-tab" + (sub === "prog" ? " on" : "")} onClick={() => setSub("prog")}>Prompt vs floor</button>
        <button className={"art-tab" + (sub === "jute" ? " on" : "")} onClick={() => setSub("jute")}>Generate · JUTE</button>
        <button className={"art-tab" + (sub === "floor" ? " on" : "")} onClick={() => setSub("floor")}>Floor contracts</button>
      </div>

      {sub === "pair" && (
        <div>
          <div className="align-card">
            <div className="ac-from">
              <div className="k">Council alone</div>
              <div className="v" style={{ color: done ? "var(--accent)" : "var(--ink)" }}>{ALIGN.before}</div>
            </div>
            <div className="ac-arrow"><Icon name="arrowR" size={18} /></div>
            <div className="ac-from ac-to">
              <div className="k">+ floor</div>
              <div className="v">{done ? ALIGN.after : "—"}</div>
            </div>
            <div className="ac-txt">
              <div className="t">{done ? "+0.50 precision on the pair" : ALIGN.label}</div>
              <div className="s">{done ? "The floor flips the false-positive and holds the genuine fabrication." : "Run the floor to ground the verdicts against the record."}</div>
            </div>
          </div>

          <div className="art-h2">By-construction pair <span className="cnt">council → + floor</span></div>
          <div className="cmp-table">
            <div className="cmp-head"><span>Note</span><span>Council</span><span>+ Floor</span><span>Change</span></div>
            {PAIR.map((p) => (
              <div className="cmp-row" key={p.id}>
                <span className="cr-name">{p.title} <span className="sc-s">· {p.sub}</span></span>
                <span className="cmp-v fail">{p.council}</span>
                <span className={"cmp-v " + (done ? (p.floor === "PASS" ? "pass" : "fail") : "pending")}>{done ? p.floor : "—"}</span>
                <span className={"cmp-tag " + (done ? (p.floor === "PASS" ? "improved" : "same") : "")}>{done ? (p.floor === "PASS" ? "↑ flipped" : "held") : "—"}</span>
              </div>
            ))}
          </div>
          <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>Same input note, one condition different. The council can't tell them apart; the floor can.</p>
        </div>
      )}

      {sub === "prog" && (
        <div>
          <div className="art-h2">Prompt vs floor <span className="cnt">real local run · 2 dose cases</span></div>
          <p className="muted" style={{ marginBottom: 12, fontSize: 12 }}>{PROGRESSION.case}</p>
          {PROGRESSION.stages.map((s) => (
            <div className="judge" key={s.lever}>
              <div className="judge-top">
                <div className="judge-av" style={{ background: s.ok ? "var(--teal)" : "var(--accent)" }}>
                  <Icon name={s.ok ? "check" : "gauge"} size={15} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div className="judge-name">{s.lever}</div>
                  <div className="judge-model">{s.sub}</div>
                </div>
                <div style={{ marginLeft: "auto", display: "flex", gap: 6, flexShrink: 0 }}>
                  <span className={"tag " + (s.ok ? "pass" : "fail")}>20→40 {s.e}</span>
                  <span className={"tag " + (s.ok ? "pass" : "fail")}>20→30 {s.w}</span>
                </div>
              </div>
              <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.5, marginTop: 2 }}>{s.note}</div>
            </div>
          ))}
          <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>{PROGRESSION.lesson}</p>
        </div>
      )}

      {sub === "floor" && (
        <div>
          <div className="art-h2">Per-finding grounding <span className="cnt">L = all-real · F = fabricated</span></div>
          {FLOOR.map((f) => (
            <div className="judge" key={f.code}>
              <div className="judge-top">
                <div className="judge-av" style={{ background: "var(--slate)" }}><Icon name="shield" size={15} /></div>
                <div style={{ minWidth: 0 }}>
                  <div className="judge-name">{f.code}</div>
                  <div className="judge-model">grounds against {f.source}</div>
                </div>
                <span className="tag" style={{ marginLeft: "auto" }}>{f.basis}</span>
              </div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted)", lineHeight: 1.6 }}>
                L: <span style={{ color: "var(--teal)" }}>{f.L}</span> · F: <span style={{ color: f.F === "retained" ? "var(--accent)" : "var(--teal)" }}>{f.F}</span>
              </div>
            </div>
          ))}
          <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>FABRICATED_HISTORY + HALLUCINATED_DETAIL are <b>retained</b> on the fabricated note (diabetes ∉ record) — that's why F stays BLOCK. No false-regression.</p>
        </div>
      )}

      {sub === "jute" && (
        <div>
          <div className="art-h2">The prompt our generator built <span className="cnt">verbatim · jute_dspy.py + live :3031</span></div>
          <div className="icard" style={{ marginBottom: 16, padding: "11px 13px", fontSize: 12, lineHeight: 1.5 }}>
            <div style={{ marginBottom: 9 }}><div className="sc-s" style={{ marginBottom: 2 }}>TASK</div>{JUTE_PROMPT.task}</div>
            <div style={{ marginBottom: 9 }}><div className="sc-s" style={{ marginBottom: 2 }}>YOUR CONTRACT · plain rules</div>{JUTE_PROMPT.contract}</div>
            <div style={{ marginBottom: 9 }}><div className="sc-s" style={{ marginBottom: 2, color: "var(--teal)" }}>GROUNDED IN WHAT THE ENGINE ACTUALLY RUNS</div><span style={{ fontFamily: "var(--mono)", fontSize: 11 }}>{JUTE_PROMPT.works}</span></div>
            <div style={{ marginBottom: 9 }}><div className="sc-s" style={{ marginBottom: 2, color: "var(--accent)" }}>NOT THESE · the served spec lies</div>{JUTE_PROMPT.fails}</div>
            <div><div className="sc-s" style={{ marginBottom: 2 }}>REFINE · the live engine error fed back</div>{JUTE_PROMPT.refine}</div>
          </div>
          <div className="art-h2">Run · the bench-gate decides <span className="cnt">live · :3031 + DSPy</span></div>
          <p className="muted" style={{ marginBottom: 6, fontSize: 12 }}>{JUTE_RUN.contract}</p>
          <p className="muted" style={{ marginBottom: 12, fontSize: 11.5, opacity: 0.8 }}>{JUTE_RUN.gate}</p>
          {JUTE_RUN.rows.map((r) => (
            <div className="judge" key={r.path}>
              <div className="judge-top">
                <div className="judge-av" style={{ background: r.ok ? "var(--teal)" : "var(--accent)" }}>
                  <Icon name={r.ok ? "check" : "gauge"} size={15} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div className="judge-name">{r.path}</div>
                  <div className="judge-model">{r.result}</div>
                </div>
                <span className={"tag " + (r.ok ? "pass" : "fail")} style={{ marginLeft: "auto" }}>{r.ok ? "ACCEPT" : "reject"}</span>
              </div>
            </div>
          ))}
          <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>{JUTE_RUN.lesson}</p>
          <LithrimNotes beat="jute" />
        </div>
      )}
    </div>
  );
}
