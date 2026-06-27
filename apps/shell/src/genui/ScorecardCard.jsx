/* ScorecardCard.jsx — datapoint component (tool-scorecard, RUN-ALL-1).
   Renders the consolidated cohort scorecard the BFF returns from POST /v1/cases/grade
   (the `scorecard` field): per-case caught/missed/spurious vs gold + headline flag
   precision/recall + verdict accuracy. case_id-attributed by construction — no
   span-matching. Honest-unlabeled: an unlabeled case shows its result but no accuracy.
   renderTool spreads part.output as props (flat). [[no-static-components-in-live-eval-ui]] */
import { registerTool } from "./registry.js";
import { flagLabel, verdictLabel } from "./copy.js";

const VOTE_COLOR = { PASS: "var(--teal)", WARN: "var(--amber)", FAIL: "var(--accent)", BLOCK: "var(--accent)", REJECT: "var(--accent)", APPROVE: "var(--teal)" };
const vColor = (v) => VOTE_COLOR[String(v || "").toUpperCase()] || "var(--muted)";
const pct = (x) => (x == null ? "n/a" : `${Math.round(x * 100)}%`);

function Chip({ label, color, title }) {
  return (
    <span title={title} className="inline-block rounded-[var(--radius-sm)] px-1.5 py-0.5 text-[10px] font-[family-name:var(--font-mono)]"
      style={{ background: "var(--surface-muted)", color: color || "var(--ink)", border: `1px solid ${color || "var(--border)"}` }}>
      {label}
    </span>
  );
}

export default function ScorecardCard({ cases = [], flag = {}, verdict_accuracy, by_flag = {}, n_cases, n_labeled, grade_path }) {
  if (!cases.length) {
    return (
      <div className="rounded-[var(--radius)] border border-border bg-secondary px-3.5 py-3 text-xs font-[family-name:var(--font-mono)] text-muted-foreground">
        No cases graded yet — run all cases to see the consolidated scorecard.
      </div>
    );
  }
  // the worst offenders, for the headline summary (over-fired = fp, missed = fn)
  const overfired = Object.entries(by_flag).filter(([, v]) => v.fp > 0).sort((a, b) => b[1].fp - a[1].fp);
  const missed = Object.entries(by_flag).filter(([, v]) => v.fn > 0).sort((a, b) => b[1].fn - a[1].fn);

  return (
    <div data-testid="scorecard-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
      {/* ── headline ── */}
      <div className="flex items-center justify-between">
        <div className="font-[family-name:var(--font-mono)] text-[13px] font-semibold text-foreground">
          Scorecard · {n_cases ?? cases.length} cases{n_labeled != null && n_labeled !== (n_cases ?? cases.length) ? ` · ${n_labeled} labeled` : ""}
        </div>
        {grade_path && <span className="text-[10px] text-muted-foreground">{grade_path === "live" || grade_path === "in_process" ? "fresh grade" : "replay"}</span>}
      </div>
      <div className="mt-2 flex flex-wrap gap-3 font-[family-name:var(--font-mono)] text-[11px]">
        <span>precision <strong style={{ color: "var(--ink)" }}>{pct(flag.precision)}</strong> <span className="text-muted-foreground">({flag.tp}/{flag.tp + flag.fp})</span></span>
        <span>recall <strong style={{ color: "var(--ink)" }}>{pct(flag.recall)}</strong> <span className="text-muted-foreground">({flag.tp}/{flag.tp + flag.fn})</span></span>
        {verdict_accuracy && <span>verdict match <strong style={{ color: "var(--ink)" }}>{verdict_accuracy}</strong></span>}
      </div>

      {/* ── per-case rows ── */}
      <div className="mt-3 flex flex-col gap-1">
        {cases.map((c) => (
          <div key={c.case_id} data-testid={`scorecard-row-${c.case_id}`}
            className="flex items-start gap-2 rounded-[var(--radius-sm)] border border-border bg-secondary px-2.5 py-1.5">
            <span className="min-w-0 flex-1 truncate font-[family-name:var(--font-mono)] text-[11px] text-foreground" title={c.case_id}>{c.case_id}</span>
            <span className="text-[10.5px] font-semibold" style={{ color: vColor(c.verdict) }}>{verdictLabel(c.verdict)}</span>
            <div className="flex max-w-[55%] flex-wrap justify-end gap-1">
              {!c.labeled && <span className="text-[10px] text-muted-foreground">unlabeled</span>}
              {(c.caught || []).map((f) => <Chip key={"c" + f} label={flagLabel(f)} color="var(--teal)" title="caught (in gold)" />)}
              {(c.missed || []).map((f) => <Chip key={"m" + f} label={"miss " + flagLabel(f)} color="var(--amber)" title="missed (gold, not raised)" />)}
              {(c.spurious || []).map((f) => <Chip key={"s" + f} label={"FP " + flagLabel(f)} color="var(--accent)" title="false positive (raised, not in gold)" />)}
              {c.labeled && !(c.caught || []).length && !(c.missed || []).length && !(c.spurious || []).length && <span className="text-[10px]" style={{ color: "var(--teal)" }}>clean ✓</span>}
            </div>
          </div>
        ))}
      </div>

      {/* ── over/under-fire summary ── */}
      {(overfired.length > 0 || missed.length > 0) && (
        <div className="mt-3 flex flex-col gap-1 border-t border-border pt-2 text-[10.5px] text-muted-foreground">
          {overfired.length > 0 && <div data-testid="scorecard-overfired">Over-fires: {overfired.map(([f, v]) => `${flagLabel(f)} ×${v.fp}`).join(", ")}</div>}
          {missed.length > 0 && <div data-testid="scorecard-missed">Misses: {missed.map(([f, v]) => `${flagLabel(f)} ×${v.fn}`).join(", ")}</div>}
        </div>
      )}
    </div>
  );
}

registerTool("tool-scorecard", ScorecardCard);
