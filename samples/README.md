# Sample data for the ingest front door

Drop any of these into Lithrim via the composer **📎 attach** button (or any JSON / JSONL / CSV of
your own). The front door decodes the file, generates a JUTE template that maps it into eval cases,
shows you a **preview** to validate, and loads them on **Approve**. Nothing is saved until you approve.

| File | Format | Shape | What it exercises |
|---|---|---|---|
| `quickstart/notes.jsonl` | JSONL | flat records (`id`, `note`, `transcript`) | the simplest path — one case per line, **deterministic ($0, no model key needed)** |
| `quickstart/notes.csv` | CSV | columns (`id`, `note`, `transcript`) | the CSV decode path + column → field mapping, **deterministic ($0)** |
| `arbitrary/custom_support_trace.json` | JSON | a deeply nested `{episodes:[…]}` vendor trace | the **generic** path — a fresh JUTE template for an arbitrary shape |

## How the fields map

A case needs **`case_id`**, **`response`** (the AI output being graded), and **`context`** (the source it's
graded against). For the quickstart notes: `note` → response, `transcript` → context, `id` → case_id.

If the preview's auto-detected mapping is off, use the card's **"Mapping looks wrong?"** box to describe
the fields and re-preview — e.g. for `custom_support_trace.json`:

> one case per `episodes`; case_id = eid, response = outbound.message.body, context = inbound.text

These cases are **synthetic and unlabeled** (no answer key), so grading shows verdicts but not
precision/recall — that's the honest behavior for unlabeled data. They're for trying the
ingest → grade loop; labeled corpora are authored separately.
