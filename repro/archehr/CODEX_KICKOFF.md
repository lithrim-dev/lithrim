# Continue the initial evidence-alignment experiment

Paste the following into Codex in this repository:

```text
Assess and continue the isolated ArchEHR-QA 2026 Subtask 4 experiment in repro/archehr/.
Read AGENTS.md, README.md and its required orientation documents, then
repro/archehr/ASSESSMENT.md and repro/archehr/README.md. Preserve unrelated worktree edits.

First rerun the offline smoke and the experiment tests. Verify the pinned official scorer's
SHA256 before running it on synthetic fixtures. Report the observed evidence before diagnosing
anything. The existing setup prepares inputs, deterministic feedback, council input rows and
submission files. It does NOT yet run a base model or authored council, and its synthetic score
is not a benchmark result.

Check localhost:8787/health and localhost:5180. Never autostart/restart services. An empty
archehr-initial workspace was created on _core; demo-day was deliberately left active. Read
the current state again, do not assume it is unchanged. Workspace switches are global: do not
switch/import/grade while another task is using the current workspace. Do not modify existing
agents, bindings, corpora or ontology snapshots. Never edit frozen council consensus functions.

Before a real run, obtain the authorized Task 4 dataset path, the exact release, approved model
and endpoint, allowed data handling, and an explicit spending/call limit from me. No restricted
dataset download, model download, provider spend or external data transmission without those
decisions. If unavailable, finish safe local diagnostics and report the exact missing inputs.

The task is evidence alignment, not answer generation: keep supplied answer sentences and IDs
unchanged. Adapt the authorized input with tests first; the XML adapter's current shape is based
on participant code and still needs release verification. Never read a gold key to generate
prompts, judge feedback or revisions. Keep clinical data and all derived prompts/reports in a
private controlled directory, outside tracked source. Do not assign expected_safety_flags or
constructed injection recipes to external benchmark rows.

Implement the smallest tested real-model/council adapters needed for the four-arm protocol in
ASSESSMENT.md. Capture raw predictions, actual model versions/fingerprints where available,
prompts, sampling, tokens, costs, latency and all errors. Do not drop failed cases, count cache
replays as independent runs, or label an empty submission template as a baseline. Native numeric
membership and citation-ID checks are bounded diagnostics, never semantic truth. Council
judgment must remain distinguishable from deterministic evidence. C and D must share the same
starting prediction and recorded council signals, differing only in deterministic feedback.

Use development data for iteration, then freeze the held-out protocol before inspecting its
labels/scores. Execute one affordable development pilot only within the approved budget. Score
frozen outputs through repro.archehr.official with the pinned upstream scorer; report micro-F1,
precision/recall, macro-F1, coverage, abstention, failures and cost for every arm, including losses.
Do not claim improvement from a synthetic fixture or from development tuning. Statistical
comparison and repeated held-out runs are required before publication; RL/training is out of scope.

Verify current organizer/Codabench access before promising leaderboard submission: the 2026
deadline is past. Do not publish, push, deploy, submit, or contact organizers without my approval.
Finish with working commands, test evidence, exactly what ran, and any remaining blockers.
```
