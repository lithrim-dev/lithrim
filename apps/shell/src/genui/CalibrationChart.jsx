/* CalibrationChart.jsx — datapoint component (tool-calibration_chart, SPEC §5b).
   Promoted from cards.jsx into the gen-UI registry. Kept visually faithful on the
   existing .icard chrome CSS (incremental adoption, SPEC §4). Reliability diagram:
   predicted-confidence bins vs observed accuracy. Accepts an optional curve via
   part.output (points/ece/brier); defaults to the demo CALIB curve. */
import { Icon } from "../icons.jsx";
import { CALIB } from "../data.jsx";
import { registerTool } from "./registry.js";

export default function CalibrationChart({ points, ece = "2.4%", brier = "0.061" } = {}) {
  const data = points || CALIB;
  const x0 = 40, y0 = 168, plotW = 240, plotH = 158;
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
            {[0, 0.25, 0.5, 0.75, 1].map((g) => (
              <g key={g}>
                <line x1={x0} y1={Y(g)} x2={x0 + plotW} y2={Y(g)} stroke="var(--border)" strokeWidth="1" />
                <text x={x0 - 7} y={Y(g) + 3} textAnchor="end" fontFamily="var(--mono)" fontSize="9" fill="var(--muted)">{g.toFixed(1)}</text>
                <text x={X(g)} y={y0 + 14} textAnchor="middle" fontFamily="var(--mono)" fontSize="9" fill="var(--muted)">{g.toFixed(1)}</text>
              </g>
            ))}
            <line x1={X(0)} y1={Y(0)} x2={X(1)} y2={Y(1)} stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="4 4" opacity="0.6" />
            {data.map((d, i) => (
              <rect key={i} x={X(d.p) - bw / 2} y={Y(d.o)} width={bw} height={y0 - Y(d.o)} rx="3" fill="var(--teal)" opacity="0.78" />
            ))}
            {data.map((d, i) => (
              <circle key={i} cx={X(d.p)} cy={Y(d.o)} r="3.4" fill="var(--bg)" stroke="var(--teal)" strokeWidth="2" />
            ))}
            <text x={X(0.5)} y={y0 + 28} textAnchor="middle" fontFamily="var(--mono)" fontSize="9" fill="var(--muted)">predicted confidence</text>
          </svg>
          <div className="calib-legend">
            <div className="leg-item"><span className="sw" style={{ background: "var(--teal)" }} /> observed accuracy</div>
            <div className="leg-item"><span className="sw dash" /> perfect calibration</div>
            <div className="calib-metric">
              <div className="k">Expected cal. error</div>
              <div className="v" style={{ color: "var(--teal)" }}>{ece}</div>
            </div>
            <div className="calib-metric">
              <div className="k">Brier score</div>
              <div className="v">{brier}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

registerTool("tool-calibration_chart", CalibrationChart);
