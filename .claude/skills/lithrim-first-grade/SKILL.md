---
name: lithrim-first-grade
description: Take a new Lithrim install to its first graded case. Run the zero-cost offline demo first (no key, no network), then the happy path from SETUP.md; connect the user's model key, load the quickstart sample, run one paid grade, and read the verdict and audit trail.
---

# First grade: from zero to a read verdict

Two stages: prove the loop offline for $0, then one real graded case with the user's
own model key. The paid part is one council run; the user authorizes the spend.

## 1. The $0 offline demo (no key, no network)

From a repo clone (this stage needs the source, not Docker):

```bash
git clone https://github.com/lithrim-dev/lithrim && cd lithrim
pip install -e .    # core deps only
make demo
```

Verify: the demo prints a council PASS being flipped to BLOCK by the deterministic
floor, with the findings as the why, and exits 0. That is the whole thesis in ~10
seconds: the floor overriding a confident judge, reproducibly, with no model call.

Failure handling: `pip` or Python 3.10+ missing: ask the user which Python to use; do
not install interpreters unasked. If `make` is unavailable, run
`python3 scripts/demo.py` directly (that is all the target does).

## 2. Stack up

Bring up the Docker stack if it is not already running (use the lithrim-docker-up
skill). Verify: `curl -sf http://localhost:8787/health` succeeds and
http://localhost:5180 loads.

## 3. Connect the user's model key

Grading is a live model call and needs the user's own key (OpenAI, Azure, Gemini, or an
OpenAI-compatible endpoint). Prefer having the user paste the key themselves in the UI:
session menu (bottom-left) then **Connect AI**, pick the provider, paste, save. The key
stays on their machine (a Docker volume), and also assign models under **Assign models**
in the same modal.

Env alternative (before `docker compose up`): put `OPENAI_API_KEY=...` in a `.env` next
to the compose file. Never echo the user's key into chat output or logs.

Verify: the Connect AI modal shows the provider as connected/tested.

## 4. Load the quickstart sample

In the UI: create an evaluation (left rail, **New evaluation**), then click the attach
button in the composer and pick `samples/quickstart/notes.jsonl` from the clone (or any
JSON/JSONL/CSV of the user's own). A preview card shows the extracted cases and the
generated mapping template; nothing is saved until **Approve & load** is clicked.

Failure handling: "couldn't map this file" means the mapper did not converge on the
shape; use the retry box to name the record collection and the response/context fields.
If ingestion errors, check the mapper: `curl -sf http://localhost:3031/jute-dsl-spec.json`.

## 5. Run one grade (paid, user-authorized)

In chat, ask to **grade all cases** (or use **Run live** for a single case). A
cost-confirm dialog opens: this is the user's spend, so let the USER click the
confirmation. Wait for the run to finish.

## 6. Read the verdict and the audit trail

The scorecard renders inline: per-case verdicts (the sample is unlabeled, so verdicts
without accuracy metrics is the honest display). For one case, open its run and walk
the audit record: each judge's vote with calibrated confidence, what the deterministic
floor checked and decided, and the final verdict with the why. That record is the
product: every grade is attributable, replayable evidence, not a bare score.

Wrap up by telling the user what the verdict was, what the floor did (confirmed,
suppressed, or overrode the council), and where to click to see the same trail
themselves.
