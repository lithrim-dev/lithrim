/* data.jsx — neutral placeholder content for the Lithrim shell.
   Domain content (cases, judges, flags, config) comes from the active pack + the
   config plane (the workspace's config DB), never hardcoded here. */

// The onboarding checklist shown in the left rail — domain-agnostic.
export const STEPS = [
  { name: "Domain", desc: "Install a pack or author an ontology", state: "todo" },
  { name: "Judges", desc: "Define your judge council", state: "todo" },
  { name: "Ground truth", desc: "Add an oracle / grounding floor", state: "todo" },
  { name: "Knowledge base", desc: "Index reference docs (optional)", state: "todo" },
  { name: "Run", desc: "Evaluate an agent", state: "todo" },
  { name: "Review", desc: "Inspect verdicts & report", state: "todo" },
];

// Reliability curve (predicted confidence -> observed accuracy) — demo fallback only,
// rendered when a run has no real calibration points yet.
export const CALIB = [
  { p: 0.1, o: 0.07 },
  { p: 0.3, o: 0.27 },
  { p: 0.5, o: 0.46 },
  { p: 0.7, o: 0.72 },
  { p: 0.9, o: 0.93 },
];
