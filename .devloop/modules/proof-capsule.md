# Module: proof-capsule (opt-in)

> An opinionated extension to the MONITOR close-out. Disabled by default;
> enable with `devloop init --with-proof-capsule`, or by appending this file's
> rule to `.devloop/personas/MONITOR.md`. Distilled from the workflow that
> produced this scaffold.

## The rule

At every **live attestation** (a cycle whose claim was verified against a real
run, not just tests), the monitor produces a **proof capsule** before closing:

1. A **proof doc** — `docs/research/PROOF_<stream>_<phase>_<date>.md`: the claim,
   the verbatim evidence (run id / output / diff), and the verdict.
2. *(Optional)* A **narrated artifact** (screen capture, video, or recording)
   demonstrating the live behavior, under `out/` or your evidence dir.

Template: `.devloop/templates/PROOF_CAPSULE_TEMPLATE.md` (copied in when this
module is enabled).

## Honest-Δ only

The capsule records what actually happened. **An honest loss is documented as a
loss — never dressed up as a manufactured win.** A capsule that reports a win the
evidence doesn't support is a failed capsule. This is the point of the module:
the evidence trail is only worth keeping if it's truthful, so the discipline is
to publish the real delta, positive or negative.

## Why it's a module, not core

The base workflow is domain-agnostic. Proof capsules assume you have a notion of
a "live run" to attest against and a place to keep evidence artifacts — true for
eval/research/ML work, overkill for a pure refactor stream. Enable it where live
verification is the unit of progress.

## Project specifics (lithrim-bench)

At every **A-LIVE attestation**, the proof capsule is:
- proof doc → `docs/research/PROOF_<stream>_<phase>_<date>.md`
- narrated artifact → a **zyng-narrated video** under `out/zyng_narrate/`

(Migrated from the previously baked-in `MONITOR.md` step into this module so the
generic personas can be refreshed via `devloop update` without losing it.)
