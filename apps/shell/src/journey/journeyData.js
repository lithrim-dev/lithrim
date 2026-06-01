/* journeyData.js — content for the four-act activation journey (ESM port of journeydata.jsx). */

export const ACTS = [
  { n: 1, name: "First contact", desc: "Install · pick agent · configure" },
  { n: 2, name: "The reveal", desc: "Verify an exchange — the aha" },
  { n: 3, name: "Calibration", desc: "Make the judges right" },
  { n: 4, name: "Own it", desc: "Your data · evalpack · Pro" },
];

export const PILLARS = [
  { key: "faith", name: "Faithfulness", desc: "Matches the source transcript", color: "var(--teal)", icon: "check" },
  { key: "complete", name: "Completeness", desc: "No required field omitted", color: "var(--amber)", icon: "layers" },
  { key: "safety", name: "Safety", desc: "No fabricated or unsafe claims", color: "var(--accent)", icon: "shield" },
  { key: "struct", name: "Structural", desc: "Valid note schema & sections", color: "var(--slate)", icon: "grid" },
];

export const AGENT_TYPES = [
  { id: "scribe", name: "Clinical Scribe", desc: "Drafts visit notes from a recorded encounter", icon: "note" },
  { id: "triage", name: "Triage Assistant", desc: "Routes inbound patient messages by urgency", icon: "flag" },
  { id: "intake", name: "Intake Bot", desc: "Collects history & meds before the visit", icon: "layers" },
  { id: "discharge", name: "Discharge Coach", desc: "Explains after-care instructions plainly", icon: "book" },
];

export const PACK = { name: "Healthcare Scribe Pack", ver: "v1.2.0", scenarios: 12, taxonomy: 38, judges: 4 };

// The hero exchange — a hypertension follow-up visit
export const EXCHANGE = {
  scenario: "Hypertension follow-up",
  audioLen: "4:12",
  turns: [
    { who: "clinician", t: "Good to see you again. How have the headaches been since we started the lisinopril?" },
    { who: "patient", t: "Better, honestly. Maybe once a week now instead of every day." },
    { who: "clinician", t: "Good. And you're taking it every morning — the ten milligram tablet?" },
    { who: "patient", t: "Every morning, yeah. Sometimes I forget on weekends." },
    { who: "clinician", t: "Let's keep the dose the same and recheck your pressure in six weeks." },
  ],
  // the scribe's generated note (what gets judged)
  note: {
    plan: "Continue current antihypertensive. Recheck BP in 6 weeks.",
    meds: "Lisinopril — once daily.",
    missing: "10 mg",
  },
  scores: { faith: 9.0, complete: 8.0, safety: 9.2, struct: 8.4 },
  overall: 8.6,
};

// pack scenarios with before (lenient) and after (calibrated) verdicts + ground truth
export const SCENARIOS = [
  { id: "s1", title: "Hypertension follow-up", sub: "dosage omitted", before: ["PASS", "8.6"], after: ["FAIL", "4.2"], truth: "FAIL" },
  { id: "s2", title: "Diabetes check-in", sub: "A1c + plan", before: ["PASS", "8.1"], after: ["PASS", "8.1"], truth: "PASS" },
  { id: "s3", title: "Pediatric vaccine visit", sub: "schema strict", before: ["FAIL", "5.0"], after: ["PASS", "7.8"], truth: "PASS" },
  { id: "s4", title: "Med reconciliation", sub: "missed allergy", before: ["PASS", "9.0"], after: ["FAIL", "3.6"], truth: "FAIL" },
  { id: "s5", title: "Annual physical", sub: "complete note", before: ["PASS", "8.8"], after: ["PASS", "8.5"], truth: "PASS" },
  { id: "s6", title: "Post-op wound check", sub: "follow-up set", before: ["PASS", "7.9"], after: ["PASS", "7.6"], truth: "PASS" },
];

export const ALIGN = { before: "0.62", after: "0.91" };

export const JUTE = [
  { t: "jc", v: "// compiled from plain English" },
  { t: "line", parts: [["jk", "rule"], ["jt", " "], ["jf", "completeness.medications"], ["jt", " {"]] },
  { t: "line", parts: [["jt", "  "], ["jk", "for"], ["jt", " med "], ["jk", "in"], ["jt", " note.medications:"]] },
  { t: "line", parts: [["jt", "    "], ["jk", "require"], ["jt", " med.name "], ["jk", "and"], ["jt", " med.dosage"]] },
  { t: "line", parts: [["jt", "    "], ["jk", "else"], ["jt", " "], ["jp", "fail"], ["jt", "("], ["js", "\"MED_DOSAGE_OMITTED\""], ["jt", ")"]] },
  { t: "line", parts: [["jt", "}"]] },
];

export const SDK_LINES = [
  [["ck", "import"], ["ct", " { Lithrim } "], ["ck", "from"], ["cs", " \"@lithrim/sdk\""]],
  [["ct", ""]],
  [["ck", "const"], ["ct", " bench = "], ["ck", "new"], ["cf", " Lithrim"], ["ct", "(process.env.LITHRIM_KEY)"]],
  [["cc", "// stream your real agent conversations in"]],
  [["ct", "bench."], ["cf", "capture"], ["ct", "(conversation, { agent: "], ["cs", "\"scribe-v4\""], ["ct", " })"]],
];

export const PRO_FEATURES = [
  { icon: "scale", t: "Multi-model judge council", d: "Run Claude, GPT & Gemini side-by-side and weight their votes." },
  { icon: "wand", t: "AI mappings", d: "Auto-map your schema to taxonomy codes — no manual wiring." },
  { icon: "note", t: "Shareable eval reports", d: "Export calibrated reports for your team and auditors." },
];
