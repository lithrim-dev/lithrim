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
// restarting) are absorbed with a growing wait; more than that surfaces the error.
export async function pollJob(jobId, { interval = 2000, retries = 5, onProgress } = {}) {
  let failures = 0;
  for (;;) {
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
    onProgress?.(job);
    if (job.status !== "running") return job;
    await sleep(interval);
  }
}

// Follow a job on the chip until it ends; resolves with the final record. A job that ends
// "interrupted" (the server lost its worker) is left on the chrome as resumable.
export async function followJob(job, { interval } = {}) {
  beginBatch({ total: job.total ?? null, job: job.job_id });
  try {
    const done = await pollJob(job.job_id, { interval, onProgress: (j) => updateBatch({ done: j.done, total: j.total, job: j.job_id }) });
    if (done.status === "interrupted") markInterrupted({ ...job, ...done });
    else if (done.status === "done") {
      try { window.dispatchEvent(new CustomEvent("lithrim:job-done", { detail: { job: done } })); } catch {}
    }
    return done;
  } finally {
    endBatch();
  }
}

// On mount (or an agent switch): find the agent's running or interrupted job again. Offline-safe.
export async function restoreJobs(agent, { interval } = {}) {
  let jobs;
  try { jobs = (await listJobs(agent)).jobs || []; } catch { return null; }
  const running = jobs.find((j) => j.status === "running");
  if (running) return followJob(running, { interval });
  const interrupted = jobs.find((j) => j.status === "interrupted");
  if (interrupted) markInterrupted(interrupted);
  return null;
}

// Resume an interrupted job: the server grades only the cases without a verdict.
export async function resumeJob(job, { interval } = {}) {
  const resp = await gradeCases({ agent: job.agent, resume: job.job_id, background: true });
  markInterrupted(null);
  return followJob({ ...job, ...resp }, { interval });
}
