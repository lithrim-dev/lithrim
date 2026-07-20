/* reportRead.js — NARRATIVE-LAYER-1: pure plain-language "read" builders over the REAL report
   payloads. Every sentence is computed from the data it describes; a missing field drops the
   sentence (or the whole read -> null), never a made-up number. No JSX, no fetch — unit-testable
   string builders shared by ScorecardCard, VerdictCard and the artifact pane. No em/en dashes. */
import { flagLabel, verdictLabel } from "./copy.js";

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
const word = (n) => (n >= 0 && n <= 9 ? WORDS[n] : String(n));
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const pctStr = (x) => `${Math.round(x * 100)}%`;
const uniq = (xs) => [...new Set(xs)];
const joinAnd = (xs) =>
  xs.length <= 1 ? xs.join("") : xs.length === 2 ? `${xs[0]} and ${xs[1]}` : `${xs.slice(0, -1).join(", ")}, and ${xs[xs.length - 1]}`;

function voteBucket(v) {
  const s = String(v || "").toUpperCase();
  if (["BLOCK", "FAIL", "REJECT"].includes(s)) return "block";
  if (["PASS", "APPROVE", "OK", "CLEAR"].includes(s)) return "pass";
  return "unsure";
}
const shortRole = (role) => {
  const r = String(role || "").trim().replace(/_judge$/, "").replace(/_/g, " ");
  return r ? cap(r) : "Reviewer";
};
const fullConf = (vs) => vs.length > 0 && vs.every((v) => typeof v.confidence === "number" && v.confidence >= 0.95);
const allPhrase = (m) => (m === 1 ? "The only reviewer" : m === 2 ? "Both reviewers" : `All ${word(m)} reviewers`);

// the one-clause judge-vote summary ("Risk passed it outright at full confidence, Policy and
// Faithfulness were only uncertain") — names are the short role, votes bucketed pass/unsure/block.
function judgeSummary(votes) {
  const groups = { pass: [], unsure: [], block: [] };
  votes.forEach((v) => groups[voteBucket(v.vote)].push(v));
  const nm = (v) => shortRole(v.role || v.judge_role);
  const phrases = [];
  if (groups.pass.length) phrases.push(`${joinAnd(groups.pass.map(nm))} passed it outright${fullConf(groups.pass) ? " at full confidence" : ""}`);
  if (groups.unsure.length) phrases.push(`${joinAnd(groups.unsure.map(nm))} ${groups.unsure.length > 1 ? "were" : "was"} only uncertain`);
  if (groups.block.length) phrases.push(`${joinAnd(groups.block.map(nm))} flagged it`);
  const kinds = ["pass", "unsure", "block"].filter((k) => groups[k].length);
  if (kinds.length > 1) return `The reviewers split: ${phrases.join(", ")}`;
  const m = votes.length;
  if (kinds[0] === "pass") return `${allPhrase(m)} passed it outright${fullConf(groups.pass) ? " at full confidence" : ""}`;
  if (kinds[0] === "unsure") return `${allPhrase(m)} ${m === 1 ? "was" : "were"} uncertain`;
  return `${allPhrase(m)} flagged it`;
}

// scorecardRead(payload) -> { text, hero: {pre, post}|null, trust: bool } | null.
// The cohort read: outcome tally, the judges-alone accuracy, what the floor did, the climb.
// Honesty branches: a genuine (answer-key) defect cleared is said loudly and kills the trust
// line; post <= pre never says "climbs"; a floor with no activity -> null (no band).
export function scorecardRead(p = {}) {
  const floor = p.floor || null;
  if (!floor) return null;
  const enforced = floor.enforced || 0;
  const cleared = floor.cleared || 0;
  const genuine = (floor.gold_defect_clears || []).length;
  if (!enforced && !cleared && !genuine) return null;
  const pre = typeof floor.verdict_accuracy_pre_floor === "number" ? floor.verdict_accuracy_pre_floor : null;
  const post = typeof floor.verdict_accuracy_post_floor === "number" ? floor.verdict_accuracy_post_floor : null;
  const climb = pre != null && post != null && post > pre;
  const sentences = [];
  const cases = Array.isArray(p.cases) ? p.cases : [];
  const total = p.n_cases ?? (cases.length || null);
  if (cases.length && total) {
    const up = (v) => String(v || "").toUpperCase();
    const nFlagged = cases.filter((c) => ["BLOCK", "REJECT", "FAIL"].includes(up(c.verdict))).length;
    const nLook = cases.filter((c) => ["WARN", "NEEDS_REVIEW", "REVIEW"].includes(up(c.verdict))).length;
    const nPassed = cases.length - nFlagged - nLook;
    sentences.push(`${nPassed} of ${total} note${total === 1 ? "" : "s"} passed clean, ${nFlagged} ${nFlagged === 1 ? "was" : "were"} flagged, ${nLook} need${nLook === 1 ? "s" : ""} a human look.`);
  }
  const judges = Array.isArray(p.by_judge) ? p.by_judge : [];
  if (pre != null) {
    const who = judges.length === 1 ? "the reviewer" : judges.length >= 2 ? `the ${word(judges.length)} reviewers` : "the reviewers";
    // both noise claims are evidence-gated: over-flag from the fp tallies, disagreement from
    // differing per-judge outcomes (matrix cells / matches_gold spread / majority ties).
    const overFlag = judges.some((j) => (j.over_flags || 0) > 0) || ((p.flag || {}).fp || 0) > 0;
    const disagree = judges.length >= 2 && (
      (Array.isArray(p.judge_matrix) && p.judge_matrix.some((r) => uniq((r.cells || []).map((c) => String(c.vote || "").toUpperCase()).filter(Boolean)).length > 1))
      || uniq(judges.map((j) => j.matches_gold)).length > 1
      || ((p.majority || {}).ties || 0) > 0
    );
    const clause = disagree && overFlag ? ": they disagree and they over-flag" : overFlag ? ": they over-flag" : disagree ? ": they disagree" : "";
    sentences.push(`On their own, ${who} matched the answer key ${climb ? "just " : ""}${pctStr(pre)} of the time${clause}.`);
    if (clause) sentences.push("That noise is expected, it is why the floor exists.");
  }
  const parts = [];
  if (enforced) parts.push(`enforced ${enforced} real defect${enforced === 1 ? "" : "s"} the reviewers missed`);
  if (cleared) parts.push(`cleared ${cleared} false alarm${cleared === 1 ? "" : "s"}`);
  parts.push(genuine
    ? `cleared ${genuine} genuine defect${genuine === 1 ? "" : "s"}, investigate before trusting this run`
    : "cleared zero genuine defects");
  sentences.push(`The deterministic floor ${joinAnd(parts)}.`);
  if (pre != null && post != null) {
    sentences.push(climb ? `Verdict accuracy climbs to ${pctStr(post)}.` : `Verdict accuracy moves from ${pctStr(pre)} to ${pctStr(post)}.`);
    if (climb) sentences.push("The gap is the floor doing the work the judges can't.");
  }
  return {
    text: sentences.join(" "),
    hero: pre != null && post != null ? { pre: Math.round(pre * 100), post: Math.round(post * 100) } : null,
    trust: genuine === 0,
  };
}

// caseRead({votes, floorBlocks, floorClears, verdict}) -> string | null.
// The single-case read: who wobbled, who held. Floor enforcement with no judge block is the
// wobble story; with a judge block it is independent confirmation; clears are disproofs; no
// floor events -> a one-line judge summary + the result. No votes and no floor -> null.
export function caseRead({ votes, floorBlocks, floorClears, verdict } = {}) {
  const vs = Array.isArray(votes) ? votes : [];
  const blocks = Array.isArray(floorBlocks) ? floorBlocks : [];
  const clears = Array.isArray(floorClears) ? floorClears : [];
  const summary = vs.length ? judgeSummary(vs) : null;
  if (blocks.length) {
    const names = uniq(blocks.map((b) => flagLabel(b.flag)).filter(Boolean));
    const n = blocks.length;
    if (summary && vs.some((v) => voteBucket(v.vote) === "block")) {
      return `${summary}. The floor independently confirmed it: ${names.length ? joinAnd(names) : `${n} deterministic fact-check${n === 1 ? "" : "s"}`}, pinned to the transcript.`;
    }
    const fact = `The floor didn't hesitate: ${n} deterministic fact-check${n === 1 ? "" : "s"} ${names.length ? `found ${joinAnd(names)}` : "failed"}, ${n === 1 ? "" : "each "}pinned to the transcript. That is why it is flagged.`;
    return summary ? `${summary}. On the judges alone this note slips through. ${fact} The judges wobbled, the floor held.` : fact;
  }
  if (clears.length) {
    const names = uniq(clears.map((c) => flagLabel(c.flag)).filter(Boolean));
    const n = clears.length;
    const fact = `The floor disproved ${n} false alarm${n === 1 ? "" : "s"}${names.length ? `: ${joinAnd(names)}` : ""}.`;
    return summary ? `${summary}. ${fact}` : fact;
  }
  if (!summary) return null;
  return verdict ? `${summary}. Result: ${verdictLabel(verdict)}.` : `${summary}.`;
}

// votesRead(votes) -> { text, confidenceNote: bool } | null.
// The reviewer-spread read; confidenceNote flips when any vote carries no confidence (the
// footnote: some models expose no token logprobs).
export function votesRead(votes) {
  const vs = Array.isArray(votes) ? votes : [];
  if (!vs.length) return null;
  const m = vs.length;
  let nB = 0, nU = 0, nP = 0;
  vs.forEach((v) => { const b = voteBucket(v.vote); if (b === "block") nB += 1; else if (b === "pass") nP += 1; else nU += 1; });
  const confidenceNote = vs.some((v) => v.confidence == null);
  let text;
  if (nB > 0) {
    const parts = [`${cap(word(nB))} of ${word(m)} reviewer${m === 1 ? "" : "s"} voted to block`];
    if (nU) parts.push(`${word(nU)} ${nU === 1 ? "was" : "were"} uncertain`);
    if (nP) parts.push(`${word(nP)} passed outright`);
    text = `${parts.join(", ")}.`;
  } else if (nP === m) {
    text = `${allPhrase(m)} passed it outright.`;
  } else if (nU === m) {
    text = `${allPhrase(m)} ${m === 1 ? "was" : "were"} uncertain: no single reviewer here would have blocked the note.`;
  } else {
    text = `${cap(word(nU))} of ${word(m)} reviewers ${nU === 1 ? "was" : "were"} uncertain, ${word(nP)} passed outright. This spread is the judge noise, not a verdict: no single reviewer here would have blocked the note.`;
  }
  return { text, confidenceNote };
}
