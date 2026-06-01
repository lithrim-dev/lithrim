/* data.jsx — representative content for the Lithrim shell (ported verbatim). */

export const THREADS = [
  { id: "t1", title: "Support Agent v4", sub: "Setup · step 5 of 6", meta: "running · 3m", color: "var(--accent)", active: true },
  { id: "t2", title: "Refund classifier", sub: "Passed · 0.94 acc", meta: "2h ago", color: "var(--teal)" },
  { id: "t3", title: "RAG answer quality", sub: "Running · 1,820 / 3k", meta: "live", color: "var(--amber)" },
  { id: "t4", title: "Tone & safety sweep", sub: "Needs review · 38 flags", meta: "yesterday", color: "var(--amber)" },
  { id: "t5", title: "Onboarding bot", sub: "Passed · 0.91 acc", meta: "Mon", color: "var(--teal)" },
  { id: "t6", title: "Email draft grader", sub: "Draft", meta: "Mon", color: "var(--border-strong)" },
];

export const STEPS = [
  { name: "Domain", desc: "Customer support · transcripts", state: "done" },
  { name: "Judge", desc: "Council of 3 · cross-checked", state: "done" },
  { name: "Oracle", desc: "Human labels + ground truth", state: "done" },
  { name: "Knowledge Base", desc: "12 policy docs indexed", state: "done" },
  { name: "Run", desc: "2,400 samples · in progress", state: "current" },
  { name: "Review", desc: "Inspect verdicts & report", state: "todo" },
];

export const FAILURE_MODES = [
  { name: "Hallucinated policy", val: 58, pct: 41, color: "var(--accent)" },
  { name: "Incomplete answer", val: 39, pct: 27, color: "var(--amber)" },
  { name: "Tone mismatch", val: 27, pct: 19, color: "var(--slate)" },
  { name: "Missed escalation", val: 18, pct: 13, color: "var(--teal)" },
];

export const TILES = [
  { k: "Accuracy", v: "92.4%", d: "vs oracle labels", delta: "+2.1", up: true },
  { k: "Judge agreement", v: "0.88", d: "Fleiss' κ · 3 judges", delta: "+0.04", up: true },
  { k: "Flagged", v: "142", d: "of 2,400 samples", delta: "−31", up: true },
  { k: "Median latency", v: "1.9s", d: "per sample", delta: "+0.2", up: false },
];

export const JUDGES = [
  { name: "Primary judge", model: "anthropic/claude-3.7", av: "P", avc: "var(--accent)", weight: "0.45", pass: 88, warn: 7, fail: 5 },
  { name: "Cross judge", model: "openai/gpt-4o", av: "X", avc: "var(--slate)", weight: "0.35", pass: 84, warn: 9, fail: 7 },
  { name: "Tiebreak judge", model: "google/gemini-2.0", av: "T", avc: "var(--teal)", weight: "0.20", pass: 90, warn: 6, fail: 4 },
];

// reliability curve: predicted confidence bin -> observed accuracy
export const CALIB = [
  { p: 0.1, o: 0.07 },
  { p: 0.3, o: 0.27 },
  { p: 0.5, o: 0.46 },
  { p: 0.7, o: 0.72 },
  { p: 0.9, o: 0.93 },
];

export const CONFIG_YAML = [
  { k: "domain:", v: ' "customer_support"', t: "str" },
  { k: "dataset:", v: ' "support_transcripts.jsonl"', t: "str" },
  { k: "samples:", v: " 2400", t: "num" },
  { k: "", v: "", t: "blank" },
  { k: "judge:", v: "", t: "key" },
  { k: "  council:", v: " 3", t: "num", ind: 1 },
  { k: "  aggregate:", v: ' "weighted_vote"', t: "str", ind: 1 },
  { k: "  require_agreement:", v: " 0.66", t: "num", ind: 1 },
  { k: "", v: "", t: "blank" },
  { k: "metrics:", v: "  # active checks", t: "cmt" },
  { k: "  - accuracy", v: "", t: "key", ind: 1 },
  { k: "  - tone", v: "", t: "key", ind: 1 },
  { k: "  - policy_compliance", v: "", t: "key", ind: 1 },
  { k: "", v: "", t: "blank" },
  { k: "oracle:", v: ' "human_labels.csv"', t: "str" },
  { k: "fail_fast:", v: " false", t: "bool" },
];
