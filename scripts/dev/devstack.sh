#!/usr/bin/env bash
# ============================================================================
# Lithrim dev stack — one script to start / stop / inspect the local services.
#
#   scripts/dev/devstack.sh start   [bff|ui|all]    (default target: all)
#   scripts/dev/devstack.sh stop    [bff|ui|all]
#   scripts/dev/devstack.sh restart [bff|ui|all]
#   scripts/dev/devstack.sh status
#   scripts/dev/devstack.sh health                  # BFF up? + a $0 replay grade
#   scripts/dev/devstack.sh logs    [bff|ui]        # tail -f a service log
#   scripts/dev/devstack.sh probe                   # Azure council deployment health (tiny PAID calls)
#
# Services:
#   • BFF  — uvicorn app:app  (apps/bff)  on :8787, under the `debuglithrim` pyenv,
#            in WATCH mode (--reload, scoped to apps/bff + lithrim_bench + scripts).
#            CWD = repo root so the vendored council reads its Azure config from
#            the repo-root `.env` (env_file=".env"; the council settings tolerate
#            the backend's extra vars via extra="ignore").
#   • UI   — vite dev server (apps/shell) on :5180 — HMR/watch by default.
#
# Processes are nohup-detached (survive this shell closing). Logs + pidfiles live
# in .devstack/ (gitignored). Idempotent: start no-ops if already healthy.
# ============================================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="$REPO_ROOT/.devstack"
mkdir -p "$RUN_DIR"

BFF_PORT="${LITHRIM_BFF_PORT:-8787}"
UI_PORT="${LITHRIM_UI_PORT:-5180}"
PYENV_VER="${PYENV_VERSION:-debuglithrim}"
PYENV_PREFIX="${PYENV_ROOT:-$HOME/.pyenv}/versions/$PYENV_VER"
# uvicorn resolution, machine-agnostic: explicit LITHRIM_UVICORN override → the named pyenv
# (if present) → whatever `uvicorn` resolves on PATH (venv / pipx / system).
UVICORN_BIN="${LITHRIM_UVICORN:-$PYENV_PREFIX/bin/uvicorn}"
[ -x "$UVICORN_BIN" ] || UVICORN_BIN="$(command -v uvicorn 2>/dev/null || true)"
PY_BIN="${UVICORN_BIN:+${UVICORN_BIN%/*}/python}"
[ -n "$PY_BIN" ] && [ -x "$PY_BIN" ] || PY_BIN="$(command -v python3 2>/dev/null || true)"
SHELL_DIR="$REPO_ROOT/apps/shell"

# Pack discovery for the BFF (S-BS-138). Without a packs dir the BFF boots on the neutral `_core`
# default and can't resolve a tier:pro pack (e.g. `healthcare`) → 500 on a healthcare workspace's
# grade. Honor a caller-set LITHRIM_BENCH_PACKS_DIR; else auto-discover the sibling pack repo; else
# leave UNSET so a bare CE checkout stays on `_core` (the CE-PACK-NEUTRAL-DEFAULT contract).
if [ -z "${LITHRIM_BENCH_PACKS_DIR:-}" ] && [ -d "$REPO_ROOT/../lithrim-pack-healthcare" ]; then
  LITHRIM_BENCH_PACKS_DIR="$(cd "$REPO_ROOT/.." && pwd)/lithrim-pack-healthcare"
fi
PACKS_DIR="${LITHRIM_BENCH_PACKS_DIR:-}"
# PACK-DROPIN local parity: always include the in-repo ./packs-dropin (the SAME directory
# docker-compose bind-mounts to /dropin-packs) so a pack dropped there loads under `make up`
# exactly as under `docker compose up`. Prepended so a drop-in pack wins; empty dropin → no-op.
if [ -d "$REPO_ROOT/packs-dropin" ]; then
  PACKS_DIR="$REPO_ROOT/packs-dropin${PACKS_DIR:+:$PACKS_DIR}"
fi

if [ -t 1 ]; then G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; X=$'\033[0m'; else G=; Y=; R=; D=; X=; fi
ok()   { echo "${G}✓${X} $*"; }
info() { echo "${Y}•${X} $*"; }
err()  { echo "${R}✗${X} $*" >&2; }

port_pid()    { lsof -ti tcp:"$1" -sTCP:LISTEN 2>/dev/null | head -1; }
bff_healthy() { curl -sf "http://localhost:$BFF_PORT/health" >/dev/null 2>&1; }
ui_up()       { curl -sf -o /dev/null "http://localhost:$UI_PORT" 2>/dev/null; }

wait_for() {  # $1 predicate fn, $2 max seconds
  local fn="$1" secs="${2:-30}" i=0
  while [ "$i" -lt "$((secs * 2))" ]; do "$fn" && return 0; sleep 0.5; i=$((i + 1)); done
  return 1
}

start_bff() {
  if bff_healthy; then ok "BFF already healthy on :$BFF_PORT"; return 0; fi
  if [ -z "$UVICORN_BIN" ] || [ ! -x "$UVICORN_BIN" ]; then
    err "uvicorn not found (checked \$LITHRIM_UVICORN, pyenv '$PYENV_VER', and PATH)"
    err "  → pip install -e '.[bff,council,verification]' in your active env, or set LITHRIM_UVICORN=/path/to/uvicorn"; return 1
  fi
  [ -f "$REPO_ROOT/.env" ] || info "no $REPO_ROOT/.env — provider keys live there or in the UI's Connect AI; live grades need one (replay still works)"
  if [ -n "$PACKS_DIR" ]; then info "pack discovery: LITHRIM_BENCH_PACKS_DIR=$PACKS_DIR"
  else info "pack discovery: no LITHRIM_BENCH_PACKS_DIR — BFF on the neutral _core default (tier:pro packs absent)"; fi
  info "starting BFF (uvicorn · $PYENV_VER · watch/--reload) on :$BFF_PORT …"
  # only prefix the var when discovered, so a bare CE checkout leaves it genuinely UNSET (not "")
  local pd_env=(); [ -n "$PACKS_DIR" ] && pd_env=(env "LITHRIM_BENCH_PACKS_DIR=$PACKS_DIR")
  # watch mode: --reload + --reload-dir scoped to the BFF and the Python it imports
  # (run_eval/harness/runtime) so the reloader ignores node_modules/out/.git/.devstack —
  # watching the repo root storms the reloader. The UI side (vite) is HMR by default.
  ( cd "$REPO_ROOT" && exec "${pd_env[@]}" nohup "$UVICORN_BIN" app:app --app-dir "$REPO_ROOT/apps/bff" --port "$BFF_PORT" \
      --reload --reload-dir "$REPO_ROOT/apps/bff" --reload-dir "$REPO_ROOT/lithrim_bench" --reload-dir "$REPO_ROOT/scripts" \
      >"$RUN_DIR/bff.log" 2>&1 ) &
  echo $! >"$RUN_DIR/bff.pid"
  if wait_for bff_healthy 30; then
    ok "BFF up · pid $(cat "$RUN_DIR/bff.pid") · http://localhost:$BFF_PORT · log: .devstack/bff.log"
  else
    err "BFF did not become healthy in 30s — last log lines:"; tail -n 20 "$RUN_DIR/bff.log" 2>/dev/null; return 1
  fi
}

start_ui() {
  if ui_up; then ok "UI already up on :$UI_PORT"; return 0; fi
  if [ ! -d "$SHELL_DIR/node_modules" ]; then
    info "installing UI deps (npm install) …"; ( cd "$SHELL_DIR" && npm install ) || { err "npm install failed"; return 1; }
  fi
  info "starting shell UI (vite) on :$UI_PORT …"
  ( cd "$SHELL_DIR" && exec nohup npm run dev -- --port "$UI_PORT" --strictPort \
      >"$RUN_DIR/ui.log" 2>&1 ) &
  echo $! >"$RUN_DIR/ui.pid"
  if wait_for ui_up 40; then
    ok "UI up · pid $(cat "$RUN_DIR/ui.pid") · http://localhost:$UI_PORT · log: .devstack/ui.log"
  else
    err "UI did not come up in 40s — last log lines:"; tail -n 20 "$RUN_DIR/ui.log" 2>/dev/null; return 1
  fi
}

stop_one() {  # $1 name, $2 pidfile, $3 port — kills BOTH the recorded pid and the actual port holder
  local name="$1" pf="$2" port="$3" pids="" pid lp still
  [ -f "$pf" ] && pids="$(cat "$pf" 2>/dev/null)"
  lp="$(port_pid "$port")"; [ -n "$lp" ] && pids="$pids $lp"
  pids="$(printf '%s\n' $pids | grep -E '^[0-9]+$' | sort -u)"
  if [ -z "$pids" ]; then info "$name not running"; rm -f "$pf"; return 0; fi
  for pid in $pids; do kill "$pid" 2>/dev/null; done
  sleep 1
  still="$(port_pid "$port")"; [ -n "$still" ] && { kill -9 "$still" 2>/dev/null; sleep 0.5; }
  for pid in $pids; do kill -9 "$pid" 2>/dev/null; done
  ok "stopped $name (pid $(echo $pids | tr '\n' ' '))"
  rm -f "$pf"
}

cmd_status() {
  echo "${D}repo: $REPO_ROOT${X}"
  local bpid; bpid="$(port_pid "$BFF_PORT")"
  if bff_healthy; then ok "BFF  :$BFF_PORT  healthy  (pid ${bpid:-?})"
  elif [ -n "$bpid" ]; then err "BFF  :$BFF_PORT  port held by pid $bpid but /health failing — see .devstack/bff.log"
  else info "BFF  :$BFF_PORT  down"; fi
  local upid; upid="$(port_pid "$UI_PORT")"
  if ui_up; then ok "UI   :$UI_PORT  up       (pid ${upid:-?})  http://localhost:$UI_PORT"
  else info "UI   :$UI_PORT  down"; fi
}

cmd_health() {
  if ! bff_healthy; then err "BFF down on :$BFF_PORT — run: $(basename "$0") start bff"; return 1; fi
  ok "BFF healthy — running a \$0 replay grade …"
  curl -s -X POST "http://localhost:$BFF_PORT/v1/run-eval" -H 'Content-Type: application/json' \
    -d '{"agent":"ws0_default","live":false}' --max-time 40 \
  | python3 -c "import sys,json
try: d=json.load(sys.stdin)
except Exception: print('  non-JSON response (council error?) — see .devstack/bff.log'); raise SystemExit
v=d.get('council',{}).get('votes',[])
print('  verdict=%s · grade_path=%s · %d votes' % (d.get('result',{}).get('verdict'), d.get('grade_path'), len(v)))
[print('   ', x.get('judge_role'), x.get('vote'), 'conf', x.get('confidence')) for x in v]"
}

cmd_logs() {
  case "${1:-}" in
    bff) tail -n 60 -f "$RUN_DIR/bff.log";;
    ui)  tail -n 60 -f "$RUN_DIR/ui.log";;
    *)   echo "usage: $(basename "$0") logs [bff|ui]"; return 1;;
  esac
}

cmd_probe() {
  if [ -z "$PY_BIN" ] || [ ! -x "$PY_BIN" ]; then err "python not found (checked the uvicorn env and PATH)"; return 1; fi
  info "probing each Azure council deployment (1 token each — tiny PAID calls) …"
  ( cd "$REPO_ROOT" && PYTHONPATH="$REPO_ROOT" "$PY_BIN" "$REPO_ROOT/scripts/dev/probe_azure.py" )
}

CMD="${1:-status}"; TARGET="${2:-all}"
case "$CMD" in
  start)   case "$TARGET" in bff) start_bff;; ui) start_ui;; all) start_bff; start_ui;; *) err "unknown target '$TARGET'"; exit 1;; esac; echo; cmd_status;;
  stop)    case "$TARGET" in bff) stop_one BFF "$RUN_DIR/bff.pid" "$BFF_PORT";; ui) stop_one UI "$RUN_DIR/ui.pid" "$UI_PORT";; all) stop_one BFF "$RUN_DIR/bff.pid" "$BFF_PORT"; stop_one UI "$RUN_DIR/ui.pid" "$UI_PORT";; *) err "unknown target '$TARGET'"; exit 1;; esac;;
  restart) "$0" stop "$TARGET"; "$0" start "$TARGET";;
  status)  cmd_status;;
  health)  cmd_health;;
  logs)    cmd_logs "${2:-}";;
  probe)   cmd_probe;;
  -h|--help|help) sed -n '2,40p' "$0";;
  *) err "unknown command '$CMD'"; echo "usage: $(basename "$0") {start|stop|restart|status|health|logs|probe} [bff|ui|all]"; exit 1;;
esac
