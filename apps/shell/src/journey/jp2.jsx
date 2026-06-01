/* jp2.jsx — Phase 2 (HERO): The reveal — verify an exchange (ESM port). */
import { useState, useRef, useEffect } from "react";
import { Icon } from "../icons.jsx";
import { AgentMsg } from "./chrome.jsx";
import { EXCHANGE, PILLARS, SCENARIOS } from "./journeyData.js";

const WAVE = [3,5,8,12,18,14,9,6,11,16,22,19,13,8,5,9,14,20,26,21,15,10,7,12,17,23,28,24,18,12,8,6,10,15,19,14,9,6,4,7,11,16,13,8,5];

function ScribeExchange() {
  const [playing, setPlaying] = useState(false);
  const [prog, setProg] = useState(0);
  const ref = useRef(null);
  const toggle = () => {
    if (playing) { clearInterval(ref.current); setPlaying(false); return; }
    setPlaying(true);
    ref.current = setInterval(() => setProg((p) => { if (p >= WAVE.length) { clearInterval(ref.current); setPlaying(false); return p; } return p + 1; }), 90);
  };
  useEffect(() => () => clearInterval(ref.current), []);
  return (
    <div className="icard" style={{ marginTop: 14 }}>
      <div className="icard-hd">
        <span className="ic"><Icon name="mic" size={15} /></span>
        <span className="ttl">{EXCHANGE.scenario}</span>
        <span className="sub">raw encounter · no scores yet</span>
      </div>
      <div className="icard-bd">
        <div className="transcript">
          {EXCHANGE.turns.map((t, i) => (
            <div className={"turn " + t.who} key={i}>
              <span className="sp">{t.who}</span>
              <span className="tx">{t.t}</span>
            </div>
          ))}
        </div>
        <div className="audio">
          <button className="play-btn" onClick={toggle}><Icon name={playing ? "pause" : "play"} size={15} /></button>
          <div className="wave">
            {WAVE.map((h, i) => (
              <i key={i} className={i < prog ? "on" : ""} style={{ height: Math.max(4, h) + "px" }} />
            ))}
          </div>
          <span className="time">{EXCHANGE.audioLen}</span>
        </div>
      </div>
    </div>
  );
}

export function Center2({ verify, runVerify }) {
  return (
    <div className="convo-inner">
      <AgentMsg beat="Act 2 · The reveal"
        lead="Here's a real scribe exchange from the pack. Read it first — no badges, no verdict, just the raw interaction.">
        <ScribeExchange />
      </AgentMsg>

      <AgentMsg lead="Now the moment. Verify it — and watch the council judge the note your scribe wrote.">
        <p className="muted">Four judges, one per pillar, score the generated note against the source. Hit verify when you're ready.</p>
        <div className="verify-cta">
          <button className="btn btn-primary btn-lg" onClick={runVerify} disabled={verify === "running"}>
            {verify === "running" ? <><span className="vs-ring" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} /> Verifying…</>
              : verify === "done" ? <><Icon name="refresh" size={15} /> Verify again</>
              : <><Icon name="shield" size={15} /> Verify this exchange</>}
          </button>
          <span className="hint">judges run on your key · ~3s</span>
        </div>
      </AgentMsg>

      {verify === "done" && (
        <AgentMsg lead="Verified — 8.6, a clear pass. Browse the rest of the pack the same way.">
          <p className="muted">Every scenario in the Healthcare pack is one click from a verdict. Open any of them in the panel.</p>
        </AgentMsg>
      )}
    </div>
  );
}

export function Artifact2({ verify, revealed }) {
  const sc = EXCHANGE.scores;
  return (
    <div>
      <div className="judged-note">
        <div className="jn-hd">
          <Icon name="note" size={14} style={{ color: "var(--accent)" }} />
          Scribe note <span className="lbl">under evaluation</span>
        </div>
        <div className="jn-body">
          <div className="sec">Plan</div>
          <div>{EXCHANGE.note.plan}</div>
          <div className="sec">Medications</div>
          <div>{EXCHANGE.note.meds}</div>
        </div>
      </div>

      {verify === "idle" && (
        <div className="verify-empty">
          <div className="ve-ic"><Icon name="shield" size={22} /></div>
          <div className="ve-t">Awaiting verification</div>
          <div className="ve-s">Hit <b>Verify</b> in the conversation to run the four-pillar council on this note.</div>
        </div>
      )}

      {verify !== "idle" && (
        <div>
          {PILLARS.map((p, i) => (
            <div className={"pillar-badge" + (i < revealed ? " in" : "")} key={p.key}
              style={{ display: i < revealed ? "flex" : "none" }}>
              <span className="pb-ic" style={{ background: p.color }}><Icon name={p.icon} size={16} /></span>
              <div style={{ minWidth: 0 }}>
                <div className="pb-name">{p.name}</div>
                <div className="pb-desc">{p.desc}</div>
              </div>
              <div className="pb-score"><span className="num" style={{ color: p.color }}>{sc[p.key].toFixed(1)}</span><span className="of"> / 10</span></div>
            </div>
          ))}

          {verify === "running" && revealed < 4 && (
            <div className="verify-state">
              <div className="vs-ring" />
              <div className="vs-t">Scoring {PILLARS[revealed]?.name}…</div>
              <div className="vs-s">judge {revealed + 1} of 4</div>
            </div>
          )}

          {verify === "done" && (
            <div className="verdict-banner pass" style={{ marginTop: 14 }}>
              <div className="score-big">{EXCHANGE.overall}</div>
              <div>
                <div className="vb-t">Verified · Pass</div>
                <div className="vb-s">All four pillars cleared the threshold. The note faithfully reflects the visit.</div>
              </div>
              <span className="tag pass" style={{ marginLeft: "auto", alignSelf: "flex-start" }}>PASS</span>
            </div>
          )}
        </div>
      )}

      {verify === "done" && (
        <div className="art-sec scn-strip" style={{ marginTop: 18 }}>
          <div className="art-h2">More from the pack <span className="cnt">11 more</span></div>
          {SCENARIOS.slice(1, 5).map((s) => (
            <div className="scn-card" key={s.id}>
              <div style={{ minWidth: 0 }}>
                <div className="sc-t">{s.title}</div>
                <div className="sc-s">{s.sub}</div>
              </div>
              <span className="sc-v"><span className={"tag " + (s.before[0] === "PASS" ? "pass" : "fail")}>{s.before[0]} · {s.before[1]}</span></span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
