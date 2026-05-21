#!/usr/bin/env bash
# Phase 2 item 4: N=10 sweep at pack size 50 across 4 packs.
# Run via nohup setsid so it survives any spawning session.
# Wall clock estimate: 4 packs × 500 calls × ~25s = ~14 hours.

set -eu

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
set -a; source .live_env; set +a

PY="${PY:-pyenv exec python}"
export PYENV_VERSION="${PYENV_VERSION:-debuglithrim}"

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[$START_TS] N=10 sweep starting"
echo "  packs:    scribe_v1, scheduling_v1, coding_v1, triage_v1 (size 50 each)"
echo "  runs:     N=10 per case (500 council calls per pack)"
echo "  backend:  lithrim-pipeline (live gpt-4.1)"
echo "  outputs:  out/<pack>.n10.ndjson"
echo

for p in scribe_v1 scheduling_v1 coding_v1 triage_v1; do
  PACK_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[$PACK_START] >>> $p"
  $PY scripts/run_determinism.py \
      --pack-path "out/$p.n10.jsonl" --n 10 \
      --backend lithrim-pipeline \
      --out "out/$p.n10.ndjson"
  PACK_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[$PACK_END] <<< $p done"
  echo
done

END_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[$END_TS] N=10 sweep complete"
