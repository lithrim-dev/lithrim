# `tests/fixtures/_core/` — the NEUTRAL house fixture

These files are the **domain-neutral** house fixture that ~18 PLUMBING tests use. They let
the run-id / verdict round-trip / audit-shape / suppression-wired plumbing tests run on the
neutral `_core` pack in a **bare CE checkout** (no Pro domain pack on disk) and, identically,
in dev.

Every plumbing test imports the paths + the `house_agent()` factory from
`tests/_house_fixture.py` (the single chokepoint) instead of redefining the fixture paths
locally. The genuinely domain-specific funcs (authored-assignment grades, a 23-flag domain
ontology, the by-construction demo-pair flip) still read the Pro-pack fixture (relocated with
the pack in PACK-DIST-2 D5).

## Files

- `case._core_house.jsonl` — a domain-neutral content-review case (a FABRICATED_CLAIM
  by-construction defect + a `source_facts.referenced_terms` field for the generic
  `presence_check`), modeled on the proven `tests/fixtures/standalone/case._core_fabricated_claim.jsonl`.
- `baseline._core_house.json` — a captured-PipelineResult baseline cloning the prior house
  baseline **structure** (same top-level keys) with a NEW fixed `HOUSE_RUN_ID`. It carries
  exactly **one STANDING finding** (`FABRICATED_CLAIM`, verdict=BLOCK → reject) and **one
  SUPPRESSIBLE finding** (`UNSUPPORTED_ASSERTION`, whose `source_facts.referenced_terms`
  token is present in the transcript) so `grounded_adjustments` is non-empty — the
  suppression-shape parity the chatbind2_pane / ws2 / uap5b_chat / ws4a / ws5_bff plumbing
  tests need. The three judge votes mirror the prior shape (one PASS @ 1.0, one BLOCK @ null,
  one BLOCK @ 1.0) so the degenerate N=1 calibration is `ece == 0.5` over 2 non-null
  confidences.
- `ontology._core_house.json` — the `packs/_core` flags + questions + severity_map (copied
  so the fixture does not assume a domain-pack pin) PLUS exactly ONE generic `presence_check`
  `verification_contract` on `UNSUPPORTED_ASSERTION` (`PresenceCheck` is core-generic, reused
  unchanged from `harness/grounding.py`).

These files carry ZERO domain content — the vocabulary is the neutral content-review domain.
