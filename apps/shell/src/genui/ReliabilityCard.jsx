/* ReliabilityCard.jsx — datapoint component (tool-reliability_card, RIGOR-1).
   Renders the statistical-rigour reliability metrics GET /v1/reliability/{agent} returns
   (the `metrics` payload, flat-spread) as labeled tiles WITH a plain-English glossary:
   Fleiss/Cohen kappa · 10-bin ECE + Brier · pairwise-error phi + effective independent votes ·
   floor selective-prediction · intra-judge stability. Each metric carries its own honest
   `insufficient` flag — a thin/degenerate workspace (no repeats / no gold / n too small) renders
   an honest "not enough data yet" state with the reason, NEVER a fabricated number. Bound to the
   real endpoint; no canned values. [[no-static-components-in-live-eval-ui]] */
import { registerTool } from "./registry.js";

const num = (x, dp = 3) => (x == null ? "—" : Number(x).toFixed(dp));

// A dependency-free hover tooltip (mirrors ScorecardCard's Tip so the glossary reads the same).
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

// A jargon term that reveals its plain-English definition on hover (dotted underline = "hover me").
function Term({ tip, children }) {
  return (
    <Tip text={tip}><span className="cursor-help border-b border-dotted border-muted-foreground">{children}</span></Tip>
  );
}

// One metric tile: the value when computable, an honest "not enough data" state otherwise.
// NEVER renders a fabricated number for an insufficient metric — that is the honesty contract.
function Tile({ label, tip, metric, dp = 3, suffix = "", read }) {
  const insufficient = !metric || metric.insufficient || metric.value == null;
  return (
    <div data-testid={`reliability-tile-${label}`} className="flex flex-col gap-0.5 rounded-[var(--radius-sm)] border border-border bg-secondary px-2.5 py-2">
      <div className="text-[10.5px] text-muted-foreground"><Term tip={tip}>{label}</Term></div>
      {insufficient ? (
        <div className="text-[10.5px] leading-snug" style={{ color: "var(--muted)" }}>
          <span className="italic">not enough data yet</span>
          {metric?.reason ? <span className="block text-[10px]">{metric.reason}</span> : null}
        </div>
      ) : (
        <div className="flex items-baseline gap-1.5 font-[family-name:var(--font-mono)]">
          <span className="text-[15px] font-semibold text-foreground">{num(metric.value, dp)}{suffix}</span>
          {metric.n != null && <span className="text-[10px] text-muted-foreground">n={metric.n}</span>}
          {Array.isArray(metric.ci) && <span className="text-[10px] text-muted-foreground">[{num(metric.ci[0], 2)}, {num(metric.ci[1], 2)}]</span>}
        </div>
      )}
      {read && !insufficient && <div className="text-[10px] text-muted-foreground">{read}</div>}
    </div>
  );
}

export default function ReliabilityCard({
  n_runs,
  inter_judge_kappa, cohen_kappa_vs_gold, ece, brier,
  error_phi, effective_votes, intra_judge_stability, selective_prediction,
} = {}) {
  const anyMetric = inter_judge_kappa || cohen_kappa_vs_gold || ece || brier || error_phi || effective_votes || intra_judge_stability || selective_prediction;
  if (!anyMetric) {
    return (
      <div data-testid="reliability-card" className="rounded-[var(--radius)] border border-border bg-secondary px-3.5 py-3 text-xs font-[family-name:var(--font-mono)] text-muted-foreground">
        No graded runs yet — grade this agent's cases to compute its reliability metrics here.
      </div>
    );
  }

  const sp = selective_prediction || {};
  const cov = sp.coverage;
  const cond = sp.conditional_accuracy;
  const risk = sp.selective_risk;
  const spInsufficient = sp.insufficient || (!cov && !cond);

  return (
    <div data-testid="reliability-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
      <div className="flex items-center justify-between">
        <div className="font-[family-name:var(--font-mono)] text-[13px] font-semibold text-foreground">Reliability</div>
        <span className="text-[10px] text-muted-foreground">{n_runs != null ? `${n_runs} run${n_runs === 1 ? "" : "s"}` : ""}</span>
      </div>
      <div className="mt-1 text-[10.5px] text-muted-foreground">
        Computed from this agent's own graded runs. A metric that can't be computed says so — no fabricated numbers.
      </div>

      {/* ── agreement ── */}
      <div className="mt-2 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
        <Tile label="inter-judge agreement" metric={inter_judge_kappa} read="how much the judges agree beyond chance"
          tip="Fleiss' kappa — agreement among the judges beyond what chance would give. 1 = total agreement, 0 = chance, below 0 = worse than chance. Read it as: do the reviewers actually converge, or is their agreement just luck?" />
        <Tile label="kappa vs gold" metric={cohen_kappa_vs_gold} read="how well a judge matches the answer key beyond chance"
          tip="Cohen's kappa vs the answer key — how well the judges' Passed/Flagged call matches gold, beyond chance. Higher is better; near 0 means the judge is no better than guessing against the key." />
        <Tile label="effective votes" metric={effective_votes} dp={2} read="how many INDEPENDENT judges you really have"
          tip="Effective independent votes (n_eff) — your judges' votes are correlated, so k judges are worth fewer than k independent ones. n_eff well below the judge count means the panel is echoing itself; adding more similar judges buys little." />
      </div>

      {/* ── calibration ── */}
      <div className="mt-1.5 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
        <Tile label="calibration error (ECE)" metric={ece} read="lower is better · 0 = perfectly calibrated"
          tip="Expected Calibration Error (10 bins) — the average gap between a judge's stated confidence and how often it's actually right. 0 is perfect; a large ECE means the confidence numbers are overstated (a house style, not a probability)." />
        <Tile label="Brier score" metric={brier} read="lower is better · confidence vs correctness"
          tip="Brier score — mean squared error between stated confidence and being correct. Lower is better; it rewards confidence that tracks reality and punishes confident-but-wrong verdicts." />
        <Tile label="error correlation" metric={error_phi} dp={2} read="do the judges make the SAME mistakes?"
          tip="Pairwise error correlation (phi) — do the judges fail on the same cases? Near +1 means they share blind spots (a panel won't save you); near 0 means their errors are independent (ensembling helps)." />
      </div>

      {/* ── stability ── */}
      <div className="mt-1.5 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
        <Tile label="intra-judge stability" metric={intra_judge_stability} read="does a judge give the SAME verdict on re-run?"
          tip="Within-judge stability across repeats — re-running the same case, how often does a judge land on its own most-common verdict? 1 = perfectly self-consistent. Needs repeated runs (K ≥ 2); with one run per case it can't be measured." />
      </div>

      {/* ── floor selective-prediction ── */}
      <div className="mt-2 border-t border-border pt-2">
        <div className="mb-1 text-[10.5px] font-semibold text-foreground">
          <Term tip="Selective prediction — the deterministic floor VOTES where it can ground a check and ABSTAINS where it can't. Coverage = the share of cases it spoke on; conditional accuracy = how often it's right WHEN it speaks; selective risk = 1 − that. The pattern to want: right when it speaks, silent when it can't ground.">
            deterministic floor (selective prediction)
          </Term>
        </div>
        {spInsufficient ? (
          <div className="text-[10.5px]" style={{ color: "var(--muted)" }}>
            <span className="italic">not enough data yet</span>
            {sp.reason ? <span className="block text-[10px]">{sp.reason}</span> : <span className="block text-[10px]">no floor outcomes on labeled cases yet</span>}
          </div>
        ) : (
          <div className="flex flex-wrap gap-3 font-[family-name:var(--font-mono)] text-[11px]">
            <span><span className="text-muted-foreground">coverage</span> <strong style={{ color: "var(--ink)" }}>{cov && !cov.insufficient ? `${Math.round(cov.value * 100)}%` : "—"}</strong></span>
            <span><span className="text-muted-foreground">accuracy when it speaks</span> <strong style={{ color: "var(--teal)" }}>{cond && !cond.insufficient ? `${Math.round(cond.value * 100)}%` : "not enough data yet"}</strong></span>
            {risk && !risk.insufficient && <span><span className="text-muted-foreground">selective risk</span> <strong style={{ color: "var(--accent)" }}>{`${Math.round(risk.value * 100)}%`}</strong></span>}
          </div>
        )}
      </div>
    </div>
  );
}

registerTool("tool-reliability_card", ReliabilityCard);
