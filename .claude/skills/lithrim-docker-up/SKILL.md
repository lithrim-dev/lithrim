---
name: lithrim-docker-up
description: Stand up the Lithrim Community Edition Docker stack (BFF on 8787, UI on 5180, JUTE mapper on 3031) on this machine, either from a repo clone or from the prebuilt published images, verify health, and know how to stop or reset it.
---

# Bring up the Lithrim stack

You are operating on the user's machine at the user's request; starting these services
here is the point of the skill. Never assume sudo: if a command needs elevation, stop
and tell the user what to run instead.

## 1. Preflight

Verify Docker and Compose are available and the daemon is running:

```bash
docker compose version   # Compose v2 CLI present?
docker info              # daemon reachable?
```

Failure handling: if the CLI is missing, tell the user to install Docker Desktop or
Docker Engine and stop. If the daemon is unreachable, ask the user to start Docker
(Desktop app, or their service manager on Linux); do not attempt privileged commands
yourself.

Check that ports 8787, 5180, and 3031 are free (no sudo needed):

```bash
lsof -nP -iTCP:8787 -sTCP:LISTEN; lsof -nP -iTCP:5180 -sTCP:LISTEN; lsof -nP -iTCP:3031 -sTCP:LISTEN
```

Any output means the port is taken. Report which process holds it and ask the user how
to proceed; never kill a process unasked.

## 2. Choose the path

- **Clone and build** (the user wants the source, or will modify it): from the repo
  root, the tracked `docker-compose.yml` builds images locally. First build takes
  minutes.

  ```bash
  git clone https://github.com/lithrim-dev/lithrim && cd lithrim
  docker compose up -d --build
  ```

- **Prebuilt images, no clone** (fastest path to a running stack): fetch the standalone
  compose file (it is `deploy/docker-compose.yml` in the repo) into an empty directory
  and start it. It consumes only published images.

  ```bash
  mkdir lithrim && cd lithrim
  curl -fsSLO https://raw.githubusercontent.com/lithrim-dev/lithrim/main/deploy/docker-compose.yml
  docker compose up -d
  ```

  Note: the published UI image is localhost-only by design (the BFF URL is baked at
  build time). If the user needs a non-localhost origin, use the clone-and-build path
  with the build arg described in the repo's `Dockerfile.ui`.

## 3. Health-check loop

Poll until healthy (the BFF can take ~40 s to start; a first build far longer):

```bash
for i in $(seq 1 40); do curl -sf http://localhost:8787/health && break; sleep 3; done
curl -sf http://localhost:8787/health          # BFF: must succeed
curl -sf -o /dev/null http://localhost:5180    # UI: must succeed
curl -sf -o /dev/null http://localhost:3031/jute-dsl-spec.json   # mapper (optional service)
```

Failure handling: if the BFF never comes healthy, run `docker compose ps` and
`docker compose logs bff` and report the tail to the user. A crash-looping `bff` with a
port bind error means the preflight port check was stale; re-run it.

## 4. Done: where things are

- The app: **http://localhost:5180** (open this in the browser).
- The API: http://localhost:8787 (health at /health).
- First boot auto-seeds a neutral sample workspace; no key is needed until a live grade.

## 5. Stop and reset

- Stop, keep state: `docker compose down` (evaluations, config, and UI-connected keys
  persist in named volumes).
- Full reset to the clean seed: `docker compose down -v`. Warn the user this wipes
  their evaluations and connected keys before running it.
- Upgrade: `docker compose pull && docker compose up -d` (prebuilt path) or
  `docker compose up -d --build` after a `git pull` (clone path).
