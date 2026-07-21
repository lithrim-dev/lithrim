/* progress.js — GRADE-PROGRESS-1: the module-level batch-grade in-flight store. The cohort grade
   (POST /v1/cases/grade, panes.jsx confirmPaidRun) is ONE server-side call that runs for minutes;
   once the CostModal settles there was NO chrome-level signal it is still running. This store
   lives outside React (module state + subscribe, the useSyncExternalStore contract: a fresh
   snapshot object per transition) so the StatusBar chip survives the modal closing, artifact-tab
   switches, and CenterPane remounts. Client-side v1, no backend changes: today's batch is one
   opaque span (done stays 0); tickBatch is the per-case hook for a future client-side loop. */
const IDLE = { active: false, done: 0, total: null, label: "" };
let snap = IDLE;
const listeners = new Set();
const set = (next) => {
  snap = next;
  listeners.forEach((l) => { try { l(); } catch {} });
};
export const subscribeProgress = (l) => { listeners.add(l); return () => listeners.delete(l); };
export const getProgress = () => snap;
export const beginBatch = ({ total = null, label = "grading" } = {}) => set({ active: true, done: 0, total, label });
export const tickBatch = () => { if (snap.active) set({ ...snap, done: snap.done + 1 }); };
export const endBatch = () => set(IDLE);
