/* copy.js — UX-COPY-1: the single source of user-facing LABELS. Translates engine-internal
   vocabulary (verdict/vote codes, judge role ids, flag codes) into plain language so cards never
   render raw constants. Decisions LOCKED 2026-06-27: judges → "reviewers", verdict → "result",
   BLOCK / WARN / PASS → Flagged / Needs a look / Passed.
   See docs/design/UX_COPY_REVIEW_2026-06-27.md (the terminology map). */

function sentenceCase(s) {
  const str = String(s || "").trim();
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : str;
}

// a verdict OR per-reviewer vote code -> the plain outcome word.
const VERDICT_LABELS = {
  pass: "Passed", approve: "Passed", ok: "Passed", clear: "Passed",
  block: "Flagged", reject: "Flagged", fail: "Flagged",
  warn: "Needs a look", needs_review: "Needs a look", review: "Needs a look",
};
export function verdictLabel(v) {
  const key = String(v || "").toLowerCase().replace(/\s+/g, "_");
  return VERDICT_LABELS[key] || sentenceCase(String(v || "").replace(/_/g, " ").toLowerCase());
}

// a judge role id -> a person-friendly name (faithfulness_judge -> "Faithfulness reviewer").
export function roleLabel(role) {
  const r = String(role || "").trim();
  if (!r) return "Reviewer";
  if (r === "chat_assistant") return "Assistant";
  const base = sentenceCase(r.replace(/_judge$/, "").replace(/_/g, " ").trim());
  return /_judge$/.test(r) ? `${base} reviewer` : base;
}

// Two DIFFERENT role ids can prettify to the SAME label (generalist_judge and
// generalist_reviewer both read "Generalist reviewer") — a picker rendering both must stay
// distinguishable, so colliding labels carry their role id. Non-colliding labels unchanged.
export function roleLabelsFor(roles) {
  const byLabel = {};
  (roles || []).forEach((r) => { const l = roleLabel(r); (byLabel[l] = byLabel[l] || []).push(r); });
  const out = {};
  (roles || []).forEach((r) => { const l = roleLabel(r); out[r] = byLabel[l].length > 1 ? `${l} (${r})` : l; });
  return out;
}

// a FLAG_CODE -> a readable phrase (MEDICATION_NOT_IN_TRANSCRIPT -> "Medication not in transcript").
export function flagLabel(code) {
  const s = String(code || "").trim();
  return s ? sentenceCase(s.replace(/_/g, " ").toLowerCase()) : "";
}

// a vote's why: LLM judges emit `reason`, reward-model judges `explanation` — one read so
// cards surface both identically.
export function voteReason(v) {
  const s = v?.reason || v?.explanation || "";
  return typeof s === "string" ? s : String(s);
}

// UX-COPY-ERR-1: turn a raw error (Error | string | server detail) into a CALM, user-facing line —
// never an HTTP verb/path/status, a filesystem path, JSON, or a stack. Known causes map to specific
// guidance; a short human reason (e.g. a validation message like "… already exists") is cleaned and
// KEPT; anything still path-/JSON-/stack-shaped falls back to a generic line. Log the raw separately.
export function friendlyError(err) {
  const raw = String(err?.message ?? err ?? "").trim();
  if (!raw) return "Something went wrong. Please try again.";
  const low = raw.toLowerCase();
  if (/not found in config db|agent .*not found|no such (agent|evaluation|workspace)/.test(low))
    return "This evaluation isn't set up yet — create or pick one, then try again.";
  if (/failed to fetch|networkerror|network error|err_connection|econnrefused|fetch failed/.test(low))
    return "Couldn't reach the server. Check that it's running and try again.";
  if (/\b401\b|\b403\b|unauthorized|forbidden|not signed in/.test(low))
    return "You don't have access to that. Sign in and try again.";
  if (/\b5\d\d\b|subprocess|internal server error|traceback|stack trace/.test(low))
    return "Something went wrong on the server. Please try again.";
  if (/timeout|timed out|etimedout|deadline exceeded/.test(low))
    return "That took too long. Please try again.";
  // strip an HTTP envelope ("POST /v1/x → 422:"), a JSON `detail` wrapper, and quote/brace noise,
  // then keep a SHORT, path-free human reason; otherwise fall back to generic.
  let msg = raw
    .replace(/^[a-z]+\s+\/\S*\s*(?:→|->)\s*\d{3}\s*:?\s*/i, "")
    .replace(/\{?\s*\\?["']?detail\\?["']?\s*:\s*/i, "")
    .replace(/[{}\\"']+/g, " ")
    .replace(/\b\/\S+|https?:\/\/\S+/g, " ") // drop filesystem paths / URLs
    .replace(/\s+/g, " ")
    .trim();
  if (msg && msg.length <= 160 && !/[/{}]/.test(msg))
    return sentenceCase(msg).replace(/\s*\.?$/, ".");
  return "Something went wrong. Please try again.";
}

// grade_path → the cost tag. in_process is the OSS-standalone PAID default (LAUNCH-PREP);
// only an actual replay is free — never label a paid run "free" (S-BS-110).
export function gradeTag(gp) {
  return gp === "replay" ? "Saved replay · free" : gp === "in_process" ? "Full run · paid" : "Live run · paid";
}
