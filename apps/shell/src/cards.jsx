/* cards.jsx — the inline ConfigCard summary rendered in the conversation.
   VerdictCard + CalibrationChart were promoted into the gen-UI registry (WS-5c:
   genui/VerdictCard.jsx + genui/CalibrationChart.jsx, rendered via renderTool);
   ConfigCard stays here as the inline domain-config summary. */
import { useState } from "react";
import { Icon } from "./icons.jsx";

/* ---- Domain config widget ---- */
export function ConfigCard({ onOpen }) {
  const [samples, setSamples] = useState(100);
  const [metrics, setMetrics] = useState({ Faithfulness: true, Safety: true, Structural: true, Completeness: false });
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
            <div className="select"><span>Support tickets</span><span className="chev"><Icon name="chevD" size={14} /></span></div>
          </div>
          <div className="field">
            <span className="flbl">Dataset</span>
            <div className="select"><span className="fa-mono">tickets.jsonl</span><span className="chev"><Icon name="chevD" size={14} /></span></div>
          </div>
        </div>
        <div className="field" style={{ marginBottom: 14 }}>
          <span className="flbl">Sample size — {samples.toLocaleString()}</span>
          <div className="range-row">
            <input className="slider" type="range" min="10" max="500" step="10"
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
