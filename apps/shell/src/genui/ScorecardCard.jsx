/* ScorecardCard.jsx — datapoint component (tool-scorecard, RUN-ALL-1).
   Renders the consolidated cohort scorecard the BFF returns from POST /v1/cases/grade
   (the `scorecard` field): per-case caught/missed/spurious vs gold + headline flag
   precision/recall + verdict accuracy. case_id-attributed by construction — no
   span-matching. Honest-unlabeled: an unlabeled case shows its result but no accuracy.
   renderTool spreads part.output as props (flat) + handlers; `onOpenCaseRun(case_id)`
   (threaded from the shell) opens that case's full run in the artifact pane — the
   sanctioned conversational-first drill-down (the card stays inline; the pane holds detail).
   [[no-static-components-in-live-eval-ui]] */
import { registerTool } from "./registry.js";
import { flagLabel, verdictLabel } from "./copy.js";
import { scorecardRead } from "./reportRead.js";

const VOTE_COLOR = { PASS: "var(--teal)", WARN: "var(--amber)", FAIL: "var(--accent)", BLOCK: "var(--accent)", REJECT: "var(--accent)", APPROVE: "var(--teal)" };
const vColor = (v) => VOTE_COLOR[String(v || "").toUpperCase()] || "var(--muted)";
const pct = (x) => (x == null ? "n/a" : `${Math.round(x * 100)}%`);
const norm = (v) => String(v || "").toUpperCase();

// Plain-English verdict explanation (non-tech tooltip on each row's result word).
const VERDICT_EXPLAIN = {
  PASS: "Passed — no blocking issue was found on this case.", APPROVE: "Passed — no blocking issue was found on this case.", CLEAR: "Passed — no blocking issue was found on this case.",
  BLOCK: "Flagged — at least one issue serious enough to block was found.", REJECT: "Flagged — at least one issue serious enough to block was found.", FAIL: "Flagged — at least one issue serious enough to block was found.",
  WARN: "Needs a look — the result is uncertain; a person should review it.", NEEDS_REVIEW: "Needs a look — the result is uncertain; a person should review it.",
};
const verdictExplain = (v) => VERDICT_EXPLAIN[norm(v)] || "The overall result for this case.";

const TIP = {
  precision: "Precision — of the issues the reviewers flagged, the share that were real (in the answer key). Higher means fewer false alarms.",
  recall: "Recall — of the real issues (in the answer key), the share the reviewers caught. Higher means fewer misses.",
  match: "Verdict match — how often the overall Passed / Flagged / Needs-a-look call matched the answer key.",
  units: "Finding units — sibling flags raised on the SAME evidence count as one finding, and an issue caught under a sibling name still counts as caught. The strict row above requires the exact flag name; this row is the fairer attribution view. Both are shown — neither replaces the other.",
};
const CHIP_TIP = {
  caught: "Correctly caught — this issue is in the answer key and the reviewers raised it.",
  miss: "Missed — this issue is in the answer key but the reviewers did not raise it.",
  fp: "False alarm — the reviewers raised this, but it is not in the answer key.",
};

// A dependency-free hover tooltip (named group so it doesn't collide with the row's `group`).
// Positioned above the trigger with a high z-index so it reads over neighbouring rows.
function Tip({ text, children }) {
  return (
    <span className="relative inline-flex group/tip align-baseline">
      {children}
      <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 hidden w-max max-w-[260px] -translate-x-1/2 whitespace-normal rounded-[var(--radius-sm)] bg-foreground px-2 py-1 text-left text-[10.5px] font-normal leading-snug text-background shadow-md group-hover/tip:block">
        {text}
      </span>
    </span>
  );
}

// A jargon term that reveals a plain-English tooltip on hover (dotted underline = "hover me").
function Term({ tip, children }) {
  return (
    <Tip text={tip}><span className="cursor-help border-b border-dotted border-muted-foreground">{children}</span></Tip>
  );
}

function Chip({ label, color, title }) {
  return (
    <span title={title} className="inline-block rounded-[var(--radius-sm)] px-1.5 py-0.5 text-[10px] font-[family-name:var(--font-mono)]"
      style={{ background: "var(--surface-muted)", color: color || "var(--ink)", border: `1px solid ${color || "var(--border)"}` }}>
      {label}
    </span>
  );
}

// R3: the per-sample K-split for a matrix cell (mirrors VerdictCard.sampleSplit).
function cellSplit(scoresRaw) {
  if (!Array.isArray(scoresRaw) || scoresRaw.length < 2) return null;
  let b = 0, w = 0, p = 0;
  for (const s of scoresRaw) {
    if (s <= 0.25) b += 1; else if (s >= 0.75) p += 1; else w += 1;
  }
  return [b ? `${b}B` : "", w ? `${w}R` : "", p ? `${p}P` : ""].filter(Boolean).join("/");
}

export default function ScorecardCard({ cases = [], flag = {}, units = null, verdict_accuracy, by_flag = {}, n_cases, n_labeled, grade_path, by_judge = [], majority = null, judge_matrix = [], floor = null, onOpenCaseRun }) {
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
  const clickable = typeof onOpenCaseRun === "function";
  // plain-language outcome tally for non-tech readers (always visible, no hover needed)
  const nFlagged = cases.filter((c) => ["BLOCK", "REJECT", "FAIL"].includes(norm(c.verdict))).length;
  const nLook = cases.filter((c) => ["WARN", "NEEDS_REVIEW", "REVIEW"].includes(norm(c.verdict))).length;
  const nPassed = cases.length - nFlagged - nLook;
  // NARRATIVE-LAYER-1: the plain-language read + reframed hero, computed from THIS payload —
  // null (no band) when the floor carries nothing to read. All the numbers below stay as-is.
  const read = scorecardRead({ cases, flag, verdict_accuracy, by_flag, n_cases, n_labeled, by_judge, majority, judge_matrix, floor });

  return (
    <div data-testid="scorecard-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
      {/* ── headline ── */}
      <div className="flex items-center justify-between">
        <div className="font-[family-name:var(--font-mono)] text-[13px] font-semibold text-foreground">
          Scorecard · {n_cases ?? cases.length} cases{n_labeled != null && n_labeled !== (n_cases ?? cases.length) ? ` · ${n_labeled} labeled` : ""}
        </div>
        {grade_path && <span className="text-[10px] text-muted-foreground">{grade_path === "live" || grade_path === "in_process" ? "fresh grade" : "replay"}</span>}
      </div>
      {read && (
        <div data-testid="scorecard-read" className="mt-2 rounded-[var(--radius-sm)] border border-border px-2.5 py-2" style={{ background: "var(--surface-muted)" }}>
          <div className="font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-wide text-muted-foreground">The read</div>
          {read.hero && (
            <div data-testid="scorecard-read-hero" className="mt-1 font-[family-name:var(--font-mono)]">
              <span className="text-[18px] font-semibold text-foreground">{read.hero.pre}% → {read.hero.post}%</span>
              {/* READ-ATTRIB-1: only the counterfactual pair is a floor claim; the legacy pair
                  compares two different scoring rules and must not be labeled as the floor. */}
              <span className="ml-2 text-[10.5px] text-muted-foreground">{read.hero.basis === "floor" ? "without the floor → with the floor" : "reviewers alone → after grounding"}</span>
            </div>
          )}
          <div className="mt-1 text-[11.5px] leading-relaxed text-foreground">{read.text}</div>
          {read.trust && (
            <div data-testid="scorecard-read-trust" className="mt-1 font-[family-name:var(--font-mono)] text-[10.5px]" style={{ color: "var(--teal)" }}>
              0 genuine defects ever cleared · deterministic on every run
            </div>
          )}
        </div>
      )}
      {/* plain-English outcome tally — the non-tech headline */}
      <div className="mt-1 text-[11px] text-muted-foreground">
        <span style={{ color: "var(--accent)" }}>{nFlagged} flagged</span> · {nLook} need a look · <span style={{ color: "var(--teal)" }}>{nPassed} passed</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 font-[family-name:var(--font-mono)] text-[11px]">
        <span><Term tip={TIP.precision}>precision</Term> <strong style={{ color: "var(--ink)" }}>{pct(flag.precision)}</strong> <span className="text-muted-foreground">({flag.tp}/{flag.tp + flag.fp})</span></span>
        <span><Term tip={TIP.recall}>recall</Term> <strong style={{ color: "var(--ink)" }}>{pct(flag.recall)}</strong> <span className="text-muted-foreground">({flag.tp}/{flag.tp + flag.fn})</span></span>
        {verdict_accuracy && <span><Term tip={TIP.match}>verdict match</Term> <strong style={{ color: "var(--ink)" }}>{verdict_accuracy}</strong></span>}
      </div>
      {/* FLOOR-VIS-1: the units dual-report — the family-aware attribution view NEXT TO the
          strict row above (never replacing it). Absent on legacy scorecards → honestly absent. */}
      {units && units.tp + units.fp + units.fn > 0 && (
        <div data-testid="scorecard-units" className="mt-1 flex flex-wrap gap-3 font-[family-name:var(--font-mono)] text-[11px]">
          <span><Term tip={TIP.units}>units</Term>{" "}
            precision <strong style={{ color: "var(--ink)" }}>{pct(units.precision)}</strong> <span className="text-muted-foreground">({units.tp}/{units.tp + units.fp})</span>{" "}
            · recall <strong style={{ color: "var(--ink)" }}>{pct(units.recall)}</strong> <span className="text-muted-foreground">({units.matched_gold ?? units.tp}/{(units.matched_gold ?? units.tp) + units.fn})</span>
          </span>
        </div>
      )}

      {/* ── R3: the per-reviewer table (each model scored against gold) + the majority row ── */}
      {by_judge.length > 0 && (
        <div data-testid="scorecard-by-judge" className="mt-3 border-t border-border pt-2">
          <div className="mb-1 text-[10.5px] font-semibold text-foreground">By reviewer (vs the answer key)</div>
          <div className="flex flex-col gap-0.5 font-[family-name:var(--font-mono)] text-[10.5px]">
            {by_judge.map((j) => (
              <div key={j.judge_role} data-testid={`by-judge-row-${j.judge_role}`} className="flex flex-wrap gap-x-3">
                <span className="min-w-[160px] text-foreground">{j.model || j.judge_role}</span>
                <span style={{ color: "var(--teal)" }}>{j.matches_gold}/{j.n} match</span>
                <span style={{ color: "var(--amber)" }} title="Silent misses — the reviewer passed a note the answer key rejects.">{j.misses} missed</span>
                <span style={{ color: "var(--accent)" }} title="Over-flags — the reviewer blocked a note the answer key approves.">{j.over_flags} over-flagged</span>
              </div>
            ))}
            {majority && (
              <div data-testid="by-judge-majority" className="mt-0.5 flex flex-wrap gap-x-3 border-t border-border pt-1 text-muted-foreground">
                <span className="min-w-[160px]">cross-model majority</span>
                <span>{majority.matches_gold}/{majority.n} match</span>
                <span>{majority.misses} missed · {majority.over_flags} over-flagged{majority.ties ? ` · ${majority.ties} tie${majority.ties === 1 ? "" : "s"}` : ""}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── R3: the case × reviewer matrix (vote + raw K-split per cell; gold column) ── */}
      {judge_matrix.length > 0 && (
        <div data-testid="scorecard-judge-matrix" className="mt-3 border-t border-border pt-2">
          <div className="mb-1 text-[10.5px] font-semibold text-foreground">Case × reviewer</div>
          <div className="flex flex-col gap-0.5 overflow-x-auto font-[family-name:var(--font-mono)] text-[10px]">
            {judge_matrix.map((r) => (
              <div key={r.case_id} data-testid={`judge-matrix-row-${r.case_id}`} className="flex flex-nowrap items-baseline gap-2 whitespace-nowrap">
                <span className="min-w-[130px] max-w-[130px] truncate text-foreground" title={r.case_id}>{r.case_id}</span>
                <span className="min-w-[46px]" style={{ color: r.gold ? vColor(r.gold) : "var(--muted)" }} title="The answer key's verdict for this case.">{r.gold || "—"}</span>
                {(r.cells || []).map((c) => (
                  <span key={c.judge_role} title={`${c.model || c.judge_role}${cellSplit(c.scores_raw) ? ` · per-sample ${cellSplit(c.scores_raw)}` : ""}`}>
                    <span style={{ color: vColor(c.vote) }}>{norm(c.vote).charAt(0)}</span>
                    {cellSplit(c.scores_raw) && <span className="text-muted-foreground"> {cellSplit(c.scores_raw)}</span>}
                  </span>
                ))}
                {r.majority && <span className="text-muted-foreground" title="The cross-model majority on this case.">maj {r.majority}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── R3b: the floor tallies — the thesis headline from ONE run ── */}
      {floor && (
        <div data-testid="scorecard-floor" className="mt-3 border-t border-border pt-2 text-[10.5px]">
          <div className="mb-1 font-semibold text-foreground">Deterministic floor</div>
          <div className="flex flex-wrap gap-x-3 font-[family-name:var(--font-mono)]">
            <span style={{ color: "var(--teal)" }} title="False alarms the floor disproved and cleared.">{floor.cleared} cleared</span>
            <span style={{ color: "var(--accent)" }} title="Blocks the floor enforced that the reviewers missed.">{floor.enforced} enforced</span>
            <span className="text-muted-foreground" title="Checks that declined to vote — nothing checkable (a feature, not a failure).">{floor.inconclusive} cannot-ground</span>
            {(floor.gold_defect_clears || []).length === 0
              ? <span style={{ color: "var(--teal)" }} title="The safety property: the floor never cleared a genuine (answer-key) defect.">0 genuine defects cleared ✓</span>
              : (
                <span data-testid="scorecard-gold-defect-clears" style={{ color: "var(--accent)" }}
                  title="SAFETY VIOLATION — the floor cleared a genuine (answer-key) defect.">
                  ⚠ {floor.gold_defect_clears.length} genuine defect{floor.gold_defect_clears.length === 1 ? "" : "s"} cleared: {floor.gold_defect_clears.map((g) => `${g.case_id}:${flagLabel(g.code)}`).join(", ")}
                </span>
              )}
          </div>
          {floor.verdict_accuracy_pre_floor != null && (
            <div className="mt-1 font-[family-name:var(--font-mono)] text-muted-foreground" title="Verdict accuracy vs the answer key. The reviewers' own tier rule, the severity rescore with the floor switched off, and the final verdict. Only the last two differ by the floor.">
              verdict accuracy: reviewers alone <strong style={{ color: "var(--ink)" }}>{pct(floor.verdict_accuracy_pre_floor)}</strong>
              {floor.verdict_accuracy_no_floor != null && <> · without the floor <strong style={{ color: "var(--ink)" }}>{pct(floor.verdict_accuracy_no_floor)}</strong></>}
              {" "}→ with the floor <strong style={{ color: "var(--ink)" }}>{pct(floor.verdict_accuracy_post_floor)}</strong>
            </div>
          )}
        </div>
      )}

      {/* ── per-case rows ── */}
      {clickable && <div className="mt-3 -mb-0.5 text-[10.5px] text-muted-foreground">Click any case to open its full result →</div>}
      <div className="mt-2 flex flex-col gap-1">
        {cases.map((c) => (
          <div key={c.case_id} data-testid={`scorecard-row-${c.case_id}`}
            role={clickable ? "button" : undefined} tabIndex={clickable ? 0 : undefined}
            aria-label={clickable ? `Open the full result for ${c.case_id}` : undefined}
            onClick={clickable ? () => onOpenCaseRun(c.case_id) : undefined}
            onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpenCaseRun(c.case_id); } } : undefined}
            className={"group flex items-start gap-2 rounded-[var(--radius-sm)] border border-border bg-secondary px-2.5 py-1.5 outline-none "
              + (clickable ? "cursor-pointer transition-colors hover:border-primary hover:bg-background focus-visible:border-primary" : "")}>
            <span className="min-w-0 flex-1 truncate font-[family-name:var(--font-mono)] text-[11px] text-foreground" title={c.case_id}>{c.case_id}</span>
            <span className="text-[10.5px] font-semibold" style={{ color: vColor(c.verdict) }} title={verdictExplain(c.verdict)}>{verdictLabel(c.verdict)}</span>
            <div className="flex max-w-[52%] flex-wrap justify-end gap-1">
              {!c.labeled && <span className="text-[10px] text-muted-foreground" title="No answer key for this case — the result is shown, but accuracy isn't scored.">unlabeled</span>}
              {(c.caught || []).map((f) => <Chip key={"c" + f} label={flagLabel(f)} color="var(--teal)" title={CHIP_TIP.caught} />)}
              {(c.missed || []).map((f) => <Chip key={"m" + f} label={"miss " + flagLabel(f)} color="var(--amber)" title={CHIP_TIP.miss} />)}
              {(c.spurious || []).map((f) => <Chip key={"s" + f} label={"FP " + flagLabel(f)} color="var(--accent)" title={CHIP_TIP.fp} />)}
              {c.labeled && !(c.caught || []).length && !(c.missed || []).length && !(c.spurious || []).length && <span className="text-[10px]" style={{ color: "var(--teal)" }} title="Correct — the reviewers matched the answer key on this case.">clean ✓</span>}
            </div>
            {clickable && <span aria-hidden className="self-center text-[12px] text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">→</span>}
          </div>
        ))}
      </div>

      {/* ── over/under-fire summary ── */}
      {(overfired.length > 0 || missed.length > 0) && (
        <div className="mt-3 flex flex-col gap-1 border-t border-border pt-2 text-[10.5px] text-muted-foreground">
          {overfired.length > 0 && <div data-testid="scorecard-overfired" title="False alarms — flags raised that weren't in the answer key, by type.">Over-fires: {overfired.map(([f, v]) => `${flagLabel(f)} ×${v.fp}`).join(", ")}</div>}
          {missed.length > 0 && <div data-testid="scorecard-missed" title="Misses — answer-key issues the reviewers didn't raise, by type.">Misses: {missed.map(([f, v]) => `${flagLabel(f)} ×${v.fn}`).join(", ")}</div>}
        </div>
      )}
    </div>
  );
}

registerTool("tool-scorecard", ScorecardCard);
