/* CalibrationChart.jsx — datapoint component (tool-calibration_chart, SPEC §5b).
   Renders a REAL reliability diagram only (predicted-confidence bins vs observed
   accuracy) from part.output {points, ece, brier}. No demo curve: an output-less
   mount renders an honest empty state, and the "well-calibrated" badge is driven by
   the real ECE, not a fixed green claim. [[no-static-components-in-live-eval-ui]] */
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";

export default function CalibrationChart({ points, ece, brier } = {}) {
  // Real-data only: no curve and no metrics means this was an output-less mount —
  // show an honest placeholder, not a fabricated "well-calibrated 2.4%" demo.
  if (!points && ece == null && brier == null) {
    return (
      <div className="icard">
        <div className="icard-hd"><span className="ttl">Calibration</span></div>
        <div className="icard-bd">
          <div style={{ color: "var(--muted)", fontSize: 12.5, padding: "8px 2px" }}>
            No calibration yet — run an eval on labeled data to see the council's real reliability here.
          </div>
        </div>
      </div>
    );
  }

  const data = points || [];
  const eceNum = ece != null ? parseFloat(String(ece)) : null;
  const cal = eceNum == null ? null : eceNum <= 5 ? { cls: "pass", txt: "well-calibrated" } : { cls: "fail", txt: "high ECE" };
  const metricColor = cal?.cls === "fail" ? "var(--accent)" : "var(--teal)";
  const x0 = 40, y0 = 168, plotW = 240, plotH = 158;
  const X = (v) => x0 + v * plotW;
  const Y = (v) => y0 - v * plotH;
  const bw = 26;
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic"><Icon name="bolt" size={15} /></span>
        <span className="ttl">Calibration</span>
        <span className="sub">reliability diagram</span>
        {cal && <span className="right"><span className={"tag " + cal.cls}>{cal.txt}</span></span>}
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
              <circle key={`c${i}`} cx={X(d.p)} cy={Y(d.o)} r="3.4" fill="var(--bg)" stroke="var(--teal)" strokeWidth="2" />
            ))}
            <text x={X(0.5)} y={y0 + 28} textAnchor="middle" fontFamily="var(--mono)" fontSize="9" fill="var(--muted)">predicted confidence</text>
          </svg>
          <div className="calib-legend">
            <div className="leg-item"><span className="sw" style={{ background: "var(--teal)" }} /> observed accuracy</div>
            <div className="leg-item"><span className="sw dash" /> perfect calibration</div>
            {ece != null && (
              <div className="calib-metric">
                <div className="k">Expected cal. error</div>
                <div className="v" style={{ color: metricColor }}>{ece}</div>
              </div>
            )}
            {brier != null && (
              <div className="calib-metric">
                <div className="k">Brier score</div>
                <div className="v">{brier}</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

registerTool("tool-calibration_chart", CalibrationChart);
