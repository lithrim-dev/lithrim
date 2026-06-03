# Lithrim dev-stack shortcuts — thin wrapper over scripts/dev/devstack.sh
# (recipes use the `target: ; cmd` inline form so no literal tabs are required)
DEV := scripts/dev/devstack.sh

.PHONY: up down restart status health probe logs-bff logs-ui bff ui help
help:      ; @$(DEV) help
up:        ; @$(DEV) start all      ## start BFF (:8787) + UI (:5180)
down:      ; @$(DEV) stop all       ## stop both
restart:   ; @$(DEV) restart all    ## stop + start both
status:    ; @$(DEV) status         ## ports + health
health:    ; @$(DEV) health         ## BFF up? + a $$0 replay grade
probe:     ; @$(DEV) probe          ## per-deployment Azure health (tiny paid calls)
logs-bff:  ; @$(DEV) logs bff
logs-ui:   ; @$(DEV) logs ui
bff:       ; @$(DEV) start bff
ui:        ; @$(DEV) start ui
