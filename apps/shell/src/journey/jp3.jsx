/* jp3.jsx — Phase 3 (HERO): Calibration — make the judges right (ESM port). */
import { useState } from "react";
import { Icon } from "../icons.jsx";
import { AgentMsg } from "./chrome.jsx";
import { JUTE, SCENARIOS, ALIGN, PILLARS } from "./journeyData.js";

function JuteBlock() {
  return (
    <div className="rule-jute">
      {JUTE.map((l, i) =>
        l.t === "jc" ? <div key={i} className="jc">{l.v}</div>
          : <div key={i}>{l.parts.map((p, j) => <span key={j} className={p[0]}>{p[1]}</span>)}</div>
      )}
    </div>
  );
}

export function Center3({ calib, runCalib }) {
  const [rule, setRule] = useState("A scribe note must list every medication with its name AND dosage. Missing a dosage fails Completeness.");
  return (
    <div className="convo-inner">
      <AgentMsg beat="Act 3 · Calibration"
        lead="Here's the twist: that 8.6 was wrong. The note dropped the lisinopril dosage — a real safety gap — and the judge waved it through.">
        <p className="muted">The pack ships intentionally miscalibrated. Your job is to make the judges right. Watch where the council disagrees with the ground truth:</p>
        <div className="icard" style={{ marginTop: 14, border: "none", boxShadow: "none" }}>
          <div className="miscal">
            <div className="miscal-hd"><Icon name="gauge" size={15} /> Miscalibrated · Completeness too lenient</div>
            <div className="miscal-cols">
              <div className="miscal-col">
                <div className="mc-k">Judge said</div>
                <div className="mc-v" style={{ color: "var(--teal)" }}>PASS · 8.0</div>
                <div className="mc-d">“Medications documented.”</div>
              </div>
              <div className="miscal-neq"><i>≠</i></div>
              <div className="miscal-col">
                <div className="mc-k">Ground truth</div>
                <div className="mc-v" style={{ color: "var(--accent-ink)" }}>FAIL</div>
                <div className="mc-d">Dosage <span className="miss">10 mg</span> omitted.</div>
              </div>
            </div>
          </div>
        </div>
      </AgentMsg>

      <AgentMsg lead="Tell me what “good” means here, in plain English. I'll wire it into the council.">
        <div className="icard" style={{ marginTop: 14 }}>
          <div className="rule-edit">
            <div className="re-hd">
              <span className="re-ic" style={{ background: "var(--amber)" }}><Icon name="layers" size={13} /></span>
              <span className="re-name">Completeness judge</span>
              <span className="tag warn" style={{ marginLeft: "auto" }}>editing</span>
            </div>
            <div className="rule-en">
              <span className="lbl">Your rule · plain English</span>
              <textarea rows="3" value={rule} onChange={(e) => setRule(e.target.value)} />
            </div>
            <div className="compile-arrow"><span className="wandic"><Icon name="wand" size={14} /></span> Lithrim compiles this to a structural conditional · Jute</div>
            <JuteBlock />
          </div>
        </div>
        <p className="muted" style={{ marginTop: 14 }}>I've also grounded the judge and extended the taxonomy so the failure is traceable:</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 10 }}>
          <div className="kb-row">
            <span className="kb-ic"><Icon name="book" size={15} /></span>
            <span className="kb-name">AHA_medication_guidelines.pdf</span>
            <span className="kb-meta">+ knowledge base · 28 pp</span>
          </div>
          <div className="taxo-chips">
            <span className="taxo-chip">MED_NAME_OK</span>
            <span className="taxo-chip">DOSE_PRESENT</span>
            <span className="taxo-chip new"><Icon name="plus" size={11} /> MED_DOSAGE_OMITTED</span>
            <span className="taxo-add"><Icon name="plus" size={11} /> code</span>
          </div>
        </div>
        <div className="verify-cta">
          <button className="btn btn-primary btn-lg" onClick={runCalib} disabled={calib === "running"}>
            {calib === "running" ? <><span className="vs-ring" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} /> Re-running pack…</>
              : calib === "done" ? <><Icon name="check" size={15} sw={2.4} /> Re-calibrated</>
              : <><Icon name="refresh" size={15} /> Re-run pack & compare</>}
          </button>
          <span className="hint">12 scenarios · ~40s</span>
        </div>
      </AgentMsg>

      {calib === "done" && (
        <AgentMsg lead="Agreement jumped from 0.62 to 0.91. Three verdicts flipped to match the truth — and nothing regressed.">
          <p className="muted">The dosage miss now fails Completeness, and the over-strict pediatric case relaxed. Iterate again, or take this to your own data.</p>
        </AgentMsg>
      )}
    </div>
  );
}

export function Artifact3({ calib }) {
  const [sub, setSub] = useState("compare");
  const done = calib === "done";
  const tagFor = (s) => {
    if (!done) return ["pending", "—"];
    const right = s.after[0] === s.truth, wasRight = s.before[0] === s.truth;
    if (right && !wasRight) return ["improved", "↑ fixed"];
    if (!right && wasRight) return ["regressed", "↓ regressed"];
    return ["same", "held"];
  };
  return (
    <div>
      <div className="art-tabs" style={{ marginBottom: 16 }}>
        <button className={"art-tab" + (sub === "compare" ? " on" : "")} onClick={() => setSub("compare")}>Before / after</button>
        <button className={"art-tab" + (sub === "council" ? " on" : "")} onClick={() => setSub("council")}>Judge council</button>
      </div>

      {sub === "compare" && (
        <div>
          <div className="align-card">
            <div className="ac-from">
              <div className="k">Before</div>
              <div className="v" style={{ color: done ? "var(--amber)" : "var(--ink)" }}>{ALIGN.before}</div>
            </div>
            <div className="ac-arrow"><Icon name="arrowR" size={18} /></div>
            <div className="ac-from ac-to">
              <div className="k">After</div>
              <div className="v">{done ? ALIGN.after : "—"}</div>
            </div>
            <div className="ac-txt">
              <div className="t">{done ? "+0.29 agreement with ground truth" : "Agreement with ground truth"}</div>
              <div className="s">{done ? "Calibrated judges now match the human labels on 11 of 12 scenarios." : "Re-run the pack to see how your edits land."}</div>
            </div>
          </div>

          <div className="art-h2">Per-scenario verdicts <span className="cnt">before → after</span></div>
          <div className="cmp-table">
            <div className="cmp-head"><span>Scenario</span><span>Before</span><span>After</span><span>Change</span></div>
            {SCENARIOS.map((s) => {
              const [tag, label] = tagFor(s);
              return (
                <div className="cmp-row" key={s.id}>
                  <span className="cr-name">{s.title}</span>
                  <span className={"cmp-v " + (s.before[0] === "PASS" ? "pass" : "fail")}>{s.before[0]}</span>
                  <span className={"cmp-v " + (done ? (s.after[0] === "PASS" ? "pass" : "fail") : "pending")}>{done ? s.after[0] : "—"}</span>
                  <span className={"cmp-tag " + tag}>{label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {sub === "council" && (
        <div>
          <div className="art-h2">Four judges · one per pillar</div>
          {PILLARS.map((p) => (
            <div className="judge" key={p.key}>
              <div className="judge-top">
                <div className="judge-av" style={{ background: p.color }}><Icon name={p.icon} size={15} /></div>
                <div style={{ minWidth: 0 }}>
                  <div className="judge-name">{p.name}</div>
                  <div className="judge-model">{p.key === "complete" && done ? "calibrated · +1 rule, +1 KB" : "pack default"}</div>
                </div>
                {p.key === "complete" && done
                  ? <span className="tag pass" style={{ marginLeft: "auto" }}><Icon name="check" size={11} /> tuned</span>
                  : <span className="judge-w" style={{ marginLeft: "auto" }}><span className="k">codes</span><span className="v">{p.key === "complete" ? "3" : "—"}</span></span>}
              </div>
              {p.key === "complete" && (
                <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted)", lineHeight: 1.6 }}>
                  require med.name <span style={{ color: "var(--amber)" }}>and</span> med.dosage → else <span style={{ color: "var(--accent-ink)" }}>MED_DOSAGE_OMITTED</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
