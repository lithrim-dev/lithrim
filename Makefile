# Lithrim dev-stack shortcuts — thin wrapper over scripts/dev/devstack.sh
# (recipes use the `target: ; cmd` inline form so no literal tabs are required)
DEV := scripts/dev/devstack.sh

.PHONY: up down restart status health probe logs-bff logs-ui bff ui help test lint demo
help:      ; @$(DEV) help
demo:      ; @python3 scripts/demo.py   ## $0 demo: council votes -> floor flip PASS->BLOCK -> audit (no keys, no network, no pack)
test:      ; pytest -q                ## run the suite (needs the documented extras — CONTRIBUTING.md; no key/pack: pack tests skip)
lint:      ; ruff check .             ## lint (ruff; the frozen council seam is excluded in ruff.toml)
up:        ; @$(DEV) start all      ## start BFF (:8787, watch) + UI (:5180, HMR)
down:      ; @$(DEV) stop all       ## stop both
restart:   ; @$(DEV) restart all    ## stop + start both
status:    ; @$(DEV) status         ## ports + health
health:    ; @$(DEV) health         ## BFF up? + a $$0 replay grade
probe:     ; @$(DEV) probe          ## per-deployment Azure health (tiny paid calls)
logs-bff:  ; @$(DEV) logs bff
logs-ui:   ; @$(DEV) logs ui
bff:       ; @$(DEV) start bff
ui:        ; @$(DEV) start ui
