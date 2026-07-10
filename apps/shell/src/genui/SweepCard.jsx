/* SweepCard.jsx — datapoint component (tool-sweep_card, RIGOR-1 / Q1 — NEW-G3).
   Renders the single-reviewer K-sweep self-consistency curve GET /v1/reliability/{agent}/sweep
   returns (the `sweep` payload, flat-spread): for each K = 1..k_max, the flip-rate (would you
   answer differently with fewer samples?), majority-convergence (has this K settled on the
   converged verdict?), and per-K sample variance — each with its Wilson CI. This is the
   Coin-Flip-Judge curve made a product surface: an anecdote (n=5) becomes a corpus-wide
   self-consistency plot BESIDE the frozen consensus, never replacing it.

   Honesty contract: an insufficient/thin sweep (no sampled runs) renders an honest empty state
   with the reason, NEVER a fabricated 0-curve. Bound to the real endpoint; no canned values.
   [[no-static-components-in-live-eval-ui]] Follows the LOCKED flat-spread prop convention. */
import { registerTool } from "./registry.js";

const pct = (m) => (m == null || m.insufficient || m.value == null ? "—" : `${Math.round(m.value * 100)}%`);
const num = (m, dp = 3) => (m == null || m.insufficient || m.value == null ? "—" : Number(m.value).toFixed(dp));
const ci = (m) => (Array.isArray(m?.ci) ? `[${Math.round(m.ci[0] * 100)}, ${Math.round(m.ci[1] * 100)}]` : "");

function Tip({ text, children }) {
  return (
    <span className="relative inline-flex group/tip align-baseline">
      {children}
      <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 hidden w-max max-w-[280px] -translate-x-1/2 whitespace-normal rounded-[var(--radius-sm)] bg-foreground px-2 py-1 text-left text-[10.5px] font-normal leading-snug text-background shadow-md group-hover/tip:block">
        {text}
      </span>
    </span>
  );
}

function Term({ tip, children }) {
  return <Tip text={tip}><span className="cursor-help border-b border-dotted border-muted-foreground">{children}</span></Tip>;
}

// One K row: K label + flip-rate (with CI) + majority-convergence + variance. A tiny inline bar
// tracks the flip-rate visually (a falling bar as K rises = the reviewer settling).
function SweepRow({ row }) {
  const fr = row.flip_rate;
  const frac = fr && !fr.insufficient && fr.value != null ? Math.max(0, Math.min(1, fr.value)) : 0;
  return (
    <div data-testid="sweep-row" className="grid grid-cols-[3.2rem_1fr_auto_auto] items-center gap-2 py-0.5 text-[11px] font-[family-name:var(--font-mono)]">
      <span className="text-muted-foreground">K={row.k}</span>
      <span className="flex items-center gap-1.5">
        <span className="relative h-1.5 w-full max-w-[7rem] overflow-hidden rounded-full bg-secondary">
          <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.round(frac * 100)}%`, background: "var(--accent, #b45309)" }} />
        </span>
        <span style={{ color: "var(--accent-ink)" }}>{pct(fr)}</span>
        {ci(fr) && <span className="text-[9.5px] text-muted-foreground">{ci(fr)}</span>}
      </span>
      <span title="majority-convergence" style={{ color: "var(--teal)" }}>{pct(row.majority_convergence)}</span>
      <span title="variance" className="text-muted-foreground">{num(row.variance, 2)}</span>
    </div>
  );
}

export default function SweepCard({ insufficient, k_max, series, reason } = {}) {
  const rows = Array.isArray(series) ? series : [];
  if (insufficient || rows.length === 0) {
    return (
      <div data-testid="sweep-card" className="rounded-[var(--radius)] border border-border bg-secondary px-3.5 py-3 text-xs font-[family-name:var(--font-mono)] text-muted-foreground">
        No sampled runs yet — grade this reviewer with k ≥ 2 sampling to plot its self-consistency curve here.
        {reason ? <span className="mt-1 block text-[10.5px]">{reason}</span> : null}
      </div>
    );
  }
  return (
    <div data-testid="sweep-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
      <div className="flex items-center justify-between">
        <div className="font-[family-name:var(--font-mono)] text-[13px] font-semibold text-foreground">Reliability sweep</div>
        <span className="text-[10px] text-muted-foreground">{k_max != null ? `K = 1…${k_max}` : ""}</span>
      </div>
      <div className="mt-1 text-[10.5px] text-muted-foreground">
        One reviewer, sampled K times per case — does the verdict settle as you spend more samples? Measured against the reviewer itself, beside the frozen consensus.
      </div>
      <div className="mt-2 grid grid-cols-[3.2rem_1fr_auto_auto] gap-2 border-b border-border pb-1 text-[10px] text-muted-foreground">
        <span>samples</span>
        <span><Term tip="Flip-rate — the share of cases whose majority verdict at this K disagrees with the fully-sampled (converged) verdict. High at low K = the reviewer would have answered differently with fewer samples; it should fall toward 0 as K rises. The Wilson 95% CI is shown beside it.">flip-rate</Term></span>
        <span><Term tip="Majority-convergence — the share of cases already decided AND agreeing with the fully-sampled verdict at this K. Rises to the decided-share; ties don't count as converged.">converged</Term></span>
        <span><Term tip="Variance — the mean spread of the first-K per-sample scores across cases. Zero = unanimous samples; it shrinks as sampling averages out per-call noise.">var</Term></span>
      </div>
      <div className="mt-0.5 flex flex-col">
        {rows.map((row) => <SweepRow key={row.k} row={row} />)}
      </div>
    </div>
  );
}

registerTool("tool-sweep_card", SweepCard);
