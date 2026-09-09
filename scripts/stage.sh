#!/bin/bash
# Open the talk's code in a DEDICATED VS Code instance (isolated profile — your real
# settings/extensions are untouched). Tabs open left-to-right in beat order.
#
#   ./stage.sh          open the six talk files
#   ./stage.sh --check   verify every file:line still resolves (run this in pre-flight)
#
# On stage: Cmd+1..6 jumps tabs. Cmd+K Z = zen mode. Cmd+= / Cmd+- zooms live.

set -euo pipefail
REPO="${REPO:-$HOME/Workspace/github.com/lithrim-bench}"
HERE="$(cd "$(dirname "$0")" && pwd)"
CODE="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"

# tab order = beat order
FILES=(
  "lithrim_bench/verification/snomed_floor.py:1"     # 1  what it is (docstring = your script)
  "lithrim_bench/verification/spec.py:8"             # 2  the tri-state — THE idea
  "lithrim_bench/verification/tools.py:46"           # 3  the extension point
  "packs-dropin/clinverdict/floors.py:906"           # 4  two registries, two directions
  "packs-dropin/clinverdict/tools.json:1"            # 5  the tool is declared, not coded
  "docs/ARCHITECTURE.md:9"                           # 6  the grade path
)

if [[ "${1:-}" == "--check" ]]; then
  fail=0
  for f in "${FILES[@]}"; do
    path="$REPO/${f%:*}"; line="${f##*:}"
    if [[ ! -f "$path" ]]; then echo "  MISSING  ${f%:*}"; fail=1; continue; fi
    total=$(grep -c "" "$path")
    if (( line > total )); then echo "  LINE $line > $total  ${f%:*}"; fail=1; continue; fi
    printf "  ok  %-46s :%-4s %s\n" "${f%:*}" "$line" "$(sed -n "${line}p" "$path" | cut -c1-42)"
  done
  [[ -x "$CODE" ]] && echo "  ok  VS Code CLI $("$CODE" --version | head -1)" || { echo "  MISSING VS Code CLI"; fail=1; }
  exit $fail
fi

[[ -x "$CODE" ]] || { echo "VS Code CLI not found at $CODE"; exit 1; }
args=(); for f in "${FILES[@]}"; do args+=(-g "$REPO/$f"); done
"$CODE" --user-data-dir "$HERE/vscode-talk" --extensions-dir "$HERE/vscode-talk/ext" -n "${args[@]}"

cat <<'EOF'

  six tabs open, left to right:

    Cmd+1  snomed_floor.py   what it is — read the docstring, then jump to 113 and 141
    Cmd+2  spec.py           the tri-state (line 8) — THE idea, slow down here
    Cmd+3  tools.py          the ABC (line 46) — "one method, yours goes there"
    Cmd+4  floors.py         two registries (line 906) — suppress vs floor
    Cmd+5  tools.json        the manifest — zero engine edits
    Cmd+6  ARCHITECTURE.md   the grade path — Cmd+K V renders it side by side

  Cmd+K Z  zen mode      Cmd+=  bigger      Ctrl+G  goto line

EOF
