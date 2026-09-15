# The RAGTruth loop from the shell

The same loop as [`RAGTRUTH_LOOP.md`](RAGTRUTH_LOOP.md) (load, configure, grade, calibrate,
re-grade, export, with the scorecard in both vocabularies), run from the browser on the
published Docker images, in one workspace, with your own provider key. No terminal.

**The acceptance test this page is written against:** an uninvolved person, on a fresh
`docker compose up` of the published images, with the two RAGTruth files and their own Azure
or OpenAI key entered in the provider screen, runs the loop end to end without opening a terminal,
on a 30-per-task cut (90 test cases, the calibration split beside them), from the shell alone:
load, configure, the before round, calibrate with the pin verdict shown, the after round, the
export, and the spend line, with the scorecard in both vocabularies. A page reload or a phone
reconnect during a grade returns to the running job.

## 0. What you need

- Docker with Compose v2 and the published stack up (`docker compose up` on
  [`deploy/docker-compose.yml`](../../deploy/docker-compose.yml)); the UI is at
  `http://localhost:5180`.
- An Azure OpenAI (or OpenAI) key for the judge model.
- The two RAGTruth files on your machine (MIT, ParticleMedia/RAGTruth; Wu et al.,
  arXiv:2401.00396):

  ```bash
  curl -fsSLO https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/response.jsonl
  curl -fsSLO https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/source_info.jsonl
  ```

Every paid step below opens a cost confirm first; nothing spends until you confirm it.

## 1. Pick a workspace

The first visit opens on **Where should this work live?** Pick `default` or create one (say
`ragtruth-pilot`). A workspace holds everything for one evaluation: the cases you load, the
judges, every run and grade job, the pinned demos, the corrections log, and the exports.
`⌘K → Show workspace` lists what it holds at any time.

## 2. Connect the provider

Session menu → **Connect AI**. Under **Providers** pick Azure OpenAI, enter the endpoint and
the key, save. The line under the provider says where the key in force comes from: a key
connected here overrides one set in the environment or a compose `.env` until you reconnect.

## 3. Load the dataset

`⌘K → Load a dataset`. The card lists the importers the pack declares; pick `ragtruth`
(the citation, the licence and the verdict rule are printed on the card), attach the two
files, set **Per task** to 30, leave **test** and **calibration** ticked, press **Load**. The
result line reports exactly what landed: 90 test cases and the calibration split beside them,
labels kept, every case tagged with its split. The rail's **Load** step ticks.

## 4. Configure the reviewer

`Create reviewer` (from the chat or the Judges step). Use **Load a definition** with the
reviewer definition — fetch it from the release you are running, since you have no clone:

```bash
curl -fsSLO https://raw.githubusercontent.com/lithrim-dev/lithrim/v0.1.31/examples/ragtruth/judge.ragtruth_detector.json
```

It prefills the role, the two lens codes and the prompt; review them and press **Create
reviewer**. Under **Connect AI → Assign models** bind `ragtruth_detector` to your Azure
deployment (a dated deployment pins the served version; an alias records the version observed
on the calls). On OpenAI rather than Azure, bind a dated model id (`gpt-4.1-2025-04-14`); a
floating alias is refused, because it cannot anchor a before/after. `⌘K → How the council decides` explains the rules the reviewer runs under.

## 5. The before round

On the import card press **Grade the test split (paid)**, or `⌘K → Grade all cases`. The
cost confirm names the split and the round (`before`); confirm. The status bar shows the
progress; reload the page or open it on your phone and the running job is found again. When
it finishes the scorecard card carries the per-task table (response and span precision,
recall and F1), the per-code rows with the RAGTruth terms in brackets, the verdict rule in both
vocabularies, the refused calls, and the served model versions.

## 6. Calibrate

Open the reviewer (`Judge · ragtruth_detector`). The optimize section offers **Calibrate on
the calibration split**; keep it ticked and press **Optimize**, then confirm. The result shows
the held-out delta, whether every compiled demo traces to a calibration row, and the pin
verdict: a set that does not regress the pinned one is pinned; a losing round is reported as a
loss and left unpinned. The reviewer's card reads out the pinned demos in force.

How held-out is chosen: 70% of the calibration split trains the demos and a deterministic,
source-disjoint 30% `dev` slice of it is what the pin gate scores on. The test split is not
used at all until the after round, so the before-and-after comparison is on cases no
calibration decision has seen.

For a training export (the fine-tuning file), grade the calibration split too: the import card
and `⌘K → Grade the calibration split` run it as its own paid round; its scorecard's export
offers the `paper` and `azure-chat` formats, which a test-split round never does.

## 7. The after round

On the before round's scorecard press **Grade again with the pinned demos (paid)** and
confirm. The after card sits beside the before round, per task. **$0 replay** re-derives the
floor and the review states from the saved baselines with no judge call; the card says it is
not a measurement.

## 8. Export and spend

Press **Export the graded corpus** on a round's card: the rows and their manifest are written
under the workspace's `exports/` and the card reports the row and tier counts (judge-only,
floor-proved); **Download** fetches the file. The status bar's `$ list · N runs` line is the
running spend for the agent at list price for the served model; it counts, and never
estimates, the runs it cannot price.

## What to expect

The shape of the pilot: the demos buy precision, and the summary task stays the weak face for
recall. The measured rows for the 90-case cut are kept on [`RAGTRUTH_LOOP.md`](RAGTRUTH_LOOP.md)
when the maintainer publishes them; a fresh run moves within run-to-run noise. Three things
are never hidden: a refused judge call is a miss, a cache replay is not a measurement, and a
losing calibration round stays unpinned.
