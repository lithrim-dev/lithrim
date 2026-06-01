/* jp4.jsx — Phase 4: Own it — your data, your evalpack, Pro (ESM port). */
import { Icon } from "../icons.jsx";
import { AgentMsg } from "./chrome.jsx";
import { SDK_LINES, PRO_FEATURES } from "./journeyData.js";

export function Center4() {
  return (
    <div className="convo-inner">
      <AgentMsg beat="Act 4 · Own it"
        lead="The judges are calibrated. Now point them at your agents — your data, your conversations.">
        <p className="muted">Stream interactions in with the SDK, or import a conversation log. Two lines and your real Scribe traffic flows into Bench.</p>
        <div className="icard" style={{ marginTop: 14, overflow: "hidden" }}>
          <div className="sdk-block" style={{ border: "none", borderRadius: 0 }}>
            <div className="sb-hd">
              <Icon name="link" size={13} style={{ color: "#8590A8" }} />
              <span className="fn">capture.ts</span>
              <span className="cp"><Icon name="copy" size={13} /></span>
            </div>
            <div className="sdk-code">
              {SDK_LINES.map((l, i) => (
                <div key={i}>{l.length === 1 && l[0][1] === "" ? " " : l.map((p, j) => <span key={j} className={p[0]}>{p[1]}</span>)}</div>
              ))}
            </div>
          </div>
        </div>
        <div className="found-row">
          <div className="fr-ic"><Icon name="check" size={18} sw={2.2} /></div>
          <div className="fr-big">1,240</div>
          <div style={{ minWidth: 0 }}>
            <div className="fr-t">real Scribe conversations found</div>
            <div className="fr-s">captured over the last 14 days · ready to evaluate</div>
          </div>
        </div>
      </AgentMsg>

      <AgentMsg lead="Let's promote the strongest signals into your own evalpack — golden cases and a regression suite, built from real interactions.">
        <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 9 }}>
          <div className="promote-row">
            <span className="pr-check"><Icon name="star" size={13} /></span>
            <div style={{ minWidth: 0 }}>
              <div className="pr-n">Golden cases</div>
              <div className="pr-d">Exemplary encounters your scribe nailed — the bar to hold.</div>
            </div>
            <span className="pr-count">24</span>
          </div>
          <div className="promote-row">
            <span className="pr-check" style={{ background: "var(--accent)" }}><Icon name="shield" size={13} /></span>
            <div style={{ minWidth: 0 }}>
              <div className="pr-n">Regression suite</div>
              <div className="pr-d">Past failures — dosage drops, missed allergies — that must never recur.</div>
            </div>
            <span className="pr-count">60</span>
          </div>
        </div>
      </AgentMsg>

      <AgentMsg lead="That's a calibrated evalpack built from your own agents. Unlock Pro to scale it.">
        <div className="icard" style={{ marginTop: 14, border: "none", boxShadow: "none" }}>
          <div className="pro-panel">
            <div className="pro-hd">
              <span className="pro-badge">Pro</span>
              <span className="pro-t">Take the council further</span>
            </div>
            {PRO_FEATURES.map((f) => (
              <div className="pro-feat" key={f.t}>
                <span className="pf-ic"><Icon name={f.icon} size={15} /></span>
                <div>
                  <div className="pf-t">{f.t}</div>
                  <div className="pf-d">{f.d}</div>
                </div>
              </div>
            ))}
            <div className="pro-cta">
              <button className="btn btn-primary btn-lg" style={{ width: "100%", justifyContent: "center" }}><Icon name="lock" size={15} /> Unlock Pro</button>
            </div>
          </div>
        </div>
      </AgentMsg>
    </div>
  );
}

export function Artifact4() {
  return (
    <div>
      <div className="evp-hero">
        <div className="evp-ic"><Icon name="grid" size={22} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="ph-name">Scribe-v4 · your evalpack</div>
          <div className="ph-ver">assembled from 1,240 real conversations</div>
        </div>
        <div className="ph-status"><span className="tag pass"><Icon name="check" size={11} /> live</span></div>
      </div>

      <div className="art-sec">
        <div className="art-h2">Pack contents</div>
        <div className="tiles">
          <div className="tile"><div className="tk">Golden cases</div><div className="tv">24</div><div className="td">the bar to hold</div></div>
          <div className="tile"><div className="tk">Regression suite</div><div className="tv">60</div><div className="td">must never recur</div></div>
          <div className="tile"><div className="tk">Judges</div><div className="tv">4</div><div className="td"><span style={{ color: "var(--teal)", fontWeight: 600 }}>calibrated</span></div></div>
          <div className="tile"><div className="tk">Agreement</div><div className="tv">0.91</div><div className="td">vs ground truth</div></div>
        </div>
      </div>

      <div className="art-sec" style={{ marginBottom: 4 }}>
        <div className="art-h2">Unlocked with Pro</div>
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--r)", overflow: "hidden" }}>
          {[
            ["scale", "Multi-model council", "Claude · GPT · Gemini", "var(--teal)"],
            ["wand", "AI mappings", "schema → taxonomy, auto", "var(--accent)"],
            ["note", "Eval reports", "shareable · auditable", "var(--slate)"],
          ].map(([ic, t, s, c]) => (
            <div className="pillar-row" key={t} style={{ padding: "12px 13px" }}>
              <span className="pr-ic" style={{ background: c + "22", color: c }}><Icon name={ic} size={15} /></span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="pr-name">{t}</div>
                <div className="pr-desc">{s}</div>
              </div>
              <Icon name="lock" size={14} style={{ color: "var(--muted)" }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
