/* cards.jsx — inline cards rendered between conversation messages (ported verbatim). */
import { useState } from "react";
import { Icon } from "./icons.jsx";
import { CALIB } from "./data.jsx";

/* ---- Domain config widget ---- */
export function ConfigCard({ onOpen }) {
  const [samples, setSamples] = useState(2400);
  const [metrics, setMetrics] = useState({ Accuracy: true, Tone: true, Policy: true, Latency: false });
  const toggle = (k) => setMetrics((m) => ({ ...m, [k]: !m[k] }));
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic"><Icon name="layers" size={15} /></span>
        <span className="ttl">Domain configuration</span>
        <span className="sub">step 1 · domain</span>
        <span className="right"><span className="tag pass"><Icon name="check" size={11} /> ready</span></span>
      </div>
      <div className="icard-bd">
        <div className="field-grid" style={{ marginBottom: 13 }}>
          <div className="field">
            <span className="flbl">Domain</span>
            <div className="select"><span>Customer support</span><span className="chev"><Icon name="chevD" size={14} /></span></div>
          </div>
          <div className="field">
            <span className="flbl">Dataset</span>
            <div className="select"><span className="fa-mono">support_transcripts.jsonl</span><span className="chev"><Icon name="chevD" size={14} /></span></div>
          </div>
        </div>
        <div className="field" style={{ marginBottom: 14 }}>
          <span className="flbl">Sample size — {samples.toLocaleString()} of 2,400</span>
          <div className="range-row">
            <input className="slider" type="range" min="100" max="2400" step="100"
              value={samples} onChange={(e) => setSamples(+e.target.value)} />
            <span className="val">{samples.toLocaleString()}</span>
          </div>
        </div>
        <div className="field">
          <span className="flbl">Metrics</span>
          <div className="metric-chips">
            {Object.keys(metrics).map((k) => (
              <button key={k} className={"mchip" + (metrics[k] ? " on" : "")} onClick={() => toggle(k)}>
                <span className="tick"><Icon name="check" size={9} sw={2.4} /></span>{k}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="icard-foot">
        <span className="note">~{Math.round(samples / 400)} min · est. $0.0{Math.max(1, Math.round(samples / 600))} / sample</span>
        <button className="linkb" style={{ marginLeft: "auto" }} onClick={onOpen}>
          Edit in panel <Icon name="chevR" size={13} />
        </button>
      </div>
    </div>
  );
}

/* ---- Single-sample verdict ---- */
export function VerdictCard() {
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic"><Icon name="check" size={15} /></span>
        <span className="ttl">Sample verdict</span>
        <span className="sub">#1843 · dry run</span>
        <span className="right"><span className="tag pass">PASS</span></span>
      </div>
      <div className="icard-bd">
        <div className="verdict">
          <div className="vmain">
            <div className="qline"><b>Q.</b> Customer asks to cancel an annual plan 40 days after renewal.</div>
            <div className="aline">
              “Annual plans are refundable within 30 days of renewal, so I'm not able to issue a
              refund here — but I can switch you to monthly billing or pause the account. Which works?”
            </div>
          </div>
          <div className="vside">
            <div className="vstat"><div className="k">Confidence</div><div className="v big">0.96</div></div>
            <div className="vstat">
              <div className="k">Judge agreement</div>
              <div className="v">3 / 3</div>
              <div className="agree-dots"><i className="ad" /><i className="ad" /><i className="ad" /></div>
            </div>
            <div className="vstat"><div className="k">Policy</div><div className="v" style={{ color: "var(--teal)" }}>cited ✓</div></div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- Calibration / reliability diagram ---- */
export function CalibrationChart() {
  const W = 248, H = 158, x0 = 40, y0 = 168, plotW = 240, plotH = 158;
  const X = (v) => x0 + v * plotW;
  const Y = (v) => y0 - v * plotH;
  const bw = 26;
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic"><Icon name="bolt" size={15} /></span>
        <span className="ttl">Calibration</span>
        <span className="sub">reliability · 50-sample dry run</span>
        <span className="right"><span className="tag pass">well-calibrated</span></span>
      </div>
      <div className="icard-bd">
        <div className="calib-wrap">
          <svg width="300" height="190" viewBox="0 0 300 190" style={{ flex: "0 0 auto" }}>
            {/* gridlines */}
            {[0, 0.25, 0.5, 0.75, 1].map((g) => (
              <g key={g}>
                <line x1={x0} y1={Y(g)} x2={x0 + plotW} y2={Y(g)} stroke="var(--border)" strokeWidth="1" />
                <text x={x0 - 7} y={Y(g) + 3} textAnchor="end" fontFamily="var(--mono)" fontSize="9" fill="var(--muted)">{g.toFixed(1)}</text>
                <text x={X(g)} y={y0 + 14} textAnchor="middle" fontFamily="var(--mono)" fontSize="9" fill="var(--muted)">{g.toFixed(1)}</text>
              </g>
            ))}
            {/* ideal diagonal */}
            <line x1={X(0)} y1={Y(0)} x2={X(1)} y2={Y(1)} stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 4" opacity="0.6" />
            {/* observed bars */}
            {CALIB.map((d, i) => (
              <rect key={i} x={X(d.p) - bw / 2} y={Y(d.o)} width={bw} height={y0 - Y(d.o)} rx="3"
                fill="var(--teal)" opacity="0.78" />
            ))}
            {/* observed dots */}
            {CALIB.map((d, i) => (
              <circle key={i} cx={X(d.p)} cy={Y(d.o)} r="3.4" fill="var(--bg)" stroke="var(--teal)" strokeWidth="2" />
            ))}
            <text x={X(0.5)} y={y0 + 28} textAnchor="middle" fontFamily="var(--mono)" fontSize="9" fill="var(--muted)">predicted confidence</text>
          </svg>
          <div className="calib-legend">
            <div className="leg-item"><span className="sw" style={{ background: "var(--teal)" }} /> observed accuracy</div>
            <div className="leg-item"><span className="sw dash" /> perfect calibration</div>
            <div className="calib-metric">
              <div className="k">Expected cal. error</div>
              <div className="v" style={{ color: "var(--teal)" }}>2.4%</div>
            </div>
            <div className="calib-metric">
              <div className="k">Brier score</div>
              <div className="v">0.061</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
