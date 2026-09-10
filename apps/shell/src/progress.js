/* progress.js — GRADE-PROGRESS-1: the module-level batch-grade in-flight store. The cohort grade
   (POST /v1/cases/grade, panes.jsx confirmPaidRun) is ONE server-side call that runs for minutes;
   once the CostModal settles there was NO chrome-level signal it is still running. This store
   lives outside React (module state + subscribe, the useSyncExternalStore contract: a fresh
   snapshot object per transition) so the StatusBar chip survives the modal closing, artifact-tab
   switches, and CenterPane remounts. UI-JOURNEY-1 (B2): `job` names the background job the chip
   follows (so a reload finds it again via GET /v1/jobs) and `interrupted` holds a job the server
   reports as interrupted (its worker died) so the chrome can offer a resume instead of silence. */
const IDLE = { active: false, done: 0, total: null, label: "", job: null, interrupted: null };
let snap = IDLE;
const listeners = new Set();
const set = (next) => {
  snap = next;
  listeners.forEach((l) => { try { l(); } catch {} });
};
export const subscribeProgress = (l) => { listeners.add(l); return () => listeners.delete(l); };
export const getProgress = () => snap;
export const beginBatch = ({ total = null, label = "grading", job = null } = {}) => set({ active: true, done: 0, total, label, job, interrupted: null });
export const tickBatch = () => { if (snap.active) set({ ...snap, done: snap.done + 1 }); };
// GRADE-JOB-1: the server's own done/total from GET /v1/jobs/{id} while a background grade runs.
export const updateBatch = ({ done, total, job }) => { if (snap.active) set({ ...snap, done: done ?? snap.done, total: total ?? snap.total, job: job ?? snap.job }); };
export const endBatch = () => set({ ...IDLE, interrupted: snap.interrupted });
// A job whose worker died (status "interrupted" from the server): keep it on the chrome until
// it is resumed or dismissed; a new batch clears it.
export const markInterrupted = (job) => set({ ...snap, interrupted: job ? { job_id: job.job_id, agent: job.agent, done: job.done, total: job.total, round: job.round } : null });
