/* jobs.js — UI-JOURNEY-1 (B2): the background grade job's client trail. One poller for every
   caller (the cost-confirmed cohort grade, the mount-time restore, a resume): it tolerates a
   dropped connection (a phone reconnect, a BFF restart) by retrying with backoff instead of
   throwing the job away on the first failed poll, and it feeds the StatusBar chip. A finished
   job is announced on the `lithrim:job-done` window bridge so whichever pane is mounted can
   render its scorecard. */
import { getJob, gradeCases, listJobs } from "./bff.js";
import { beginBatch, updateBatch, endBatch, markInterrupted } from "./progress.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Poll until the job leaves "running". `retries` consecutive failed polls (network down, BFF
// restarting) are absorbed with a growing wait; more than that surfaces the error. `stopped`
// (JOB-POLLER-1) ends the loop early — the caller stopped caring (an agent switch) — and
// resolves with null, so nothing is announced for a job nobody is watching any more.
export async function pollJob(jobId, { interval = 2000, retries = 5, onProgress, stopped } = {}) {
  let failures = 0;
  for (;;) {
    if (stopped?.()) return null;
    let job;
    try {
      job = await getJob(jobId);
      failures = 0;
    } catch (err) {
      failures += 1;
      if (failures > retries) throw err;
      await sleep(Math.min(interval * failures, 10000));
      continue;
    }
    if (stopped?.()) return null;
    onProgress?.(job);
    if (job.status !== "running") return job;
    await sleep(interval);
  }
}

// JOB-POLLER-1: the pollers in flight, keyed by job id. Two callers can reach the same job (the
// tab that started it and the mount-time restore) and the panes re-mount on an agent switch;
// without this each extra poller re-entered beginBatch/endBatch, so the chip flickered and one
// poller's endBatch cleared another's progress.
const inflight = new Map();

// Stop the pollers matching `pred` ({job_id, agent}): they resolve with null and announce
// nothing. Used on an agent switch, so the previous agent's job never lands in the new one's
// chrome.
export function stopFollowing(pred = () => true) {
  for (const state of inflight.values()) if (pred(state)) state.cancelled = true;
}

// Follow a job on the chip until it ends; resolves with the final record (null if it was
// stopped). A job that ends "interrupted" (the server lost its worker) is left on the chrome as
// resumable. A second follow of the same job JOINS the first instead of starting another.
export function followJob(job, { interval } = {}) {
  const already = inflight.get(job.job_id);
  if (already) return already.promise;
  const state = { job_id: job.job_id, agent: job.agent, cancelled: false };
  state.promise = (async () => {
    beginBatch({ total: job.total ?? null, job: job.job_id });
    try {
      const done = await pollJob(job.job_id, {
        interval,
        stopped: () => state.cancelled,
        onProgress: (j) => updateBatch({ done: j.done, total: j.total, job: j.job_id }),
      });
      if (!done) return null;
      if (done.status === "interrupted") markInterrupted({ ...job, ...done });
      else if (done.status === "done") {
        try { window.dispatchEvent(new CustomEvent("lithrim:job-done", { detail: { job: done } })); } catch {}
      }
      return done;
    } finally {
      inflight.delete(job.job_id);
      endBatch();
    }
  })();
  inflight.set(job.job_id, state);
  return state.promise;
}

// On mount (or an agent switch): find the agent's running or interrupted job again. Offline-safe.
export async function restoreJobs(agent, { interval } = {}) {
  stopFollowing((state) => state.agent && state.agent !== agent);  // JOB-POLLER-1: the switch
  let jobs;
  try { jobs = (await listJobs(agent)).jobs || []; } catch { return null; }
  // OPTIMIZE-JOB-1: calibration jobs share the store; the judge editor follows those.
  jobs = jobs.filter((j) => (j.kind || "grade") === "grade");
  const running = jobs.find((j) => j.status === "running");
  if (running) return followJob(running, { interval });
  const interrupted = jobs.find((j) => j.status === "interrupted");
  if (interrupted) markInterrupted(interrupted);
  return null;
}

// Resume an interrupted job: the server grades only the cases without a verdict.
// GRADE-CONFIRM-1: a resume RUNS ON THE ORIGINAL JOB'S PAID FLAGS, so it spends; `confirm` is the
// human's cost-confirm and the service refuses the resume without it. Never default it to true.
export async function resumeJob(job, { interval, confirm = false, onAccepted } = {}) {
  const resp = await gradeCases({ agent: job.agent, resume: job.job_id, background: true, confirm });
  onAccepted?.(resp);  // JOB-POLLER-1: accepted — the caller closes its dialog, the chip reports
  markInterrupted(null);
  return followJob({ ...job, ...resp }, { interval });
}
