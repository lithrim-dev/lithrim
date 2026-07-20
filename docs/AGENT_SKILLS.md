# Agent Skills

Lithrim ships three [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) for Claude
Code (and other skills-aware agents). They automate the setup paths in this repo so you can drive
Lithrim by asking, instead of copy-pasting commands:

| Skill | What it does |
|---|---|
| **`lithrim-docker-up`** | Stand up the stack (BFF `:8787`, UI `:5180`, JUTE mapper `:3031`), from a clone or the prebuilt images, verify health, and stop or reset it. |
| **`lithrim-first-grade`** | Take a new install to its first graded case: the `$0` offline demo, then connect a key, load the quickstart sample, run one paid grade, and read the verdict + audit trail. |
| **`lithrim-snomed-setup`** | Wire a local Hermes SNOMED CT terminology server into the grounding floor (licensing gate first; you bring the release, the skill builds the index, mounts it, authors the tool, and verifies one lookup). |

The skills live in [`.claude/skills/`](../.claude/skills/) and are the only tracked part of
`.claude/`. They are plain Markdown (`SKILL.md`) with YAML frontmatter, so they work with any tool
that reads the Agent Skills format.

---

## Install

### If you cloned the repo (project-scoped, zero setup)

Open Claude Code with this repo as the working directory. Project skills under `.claude/skills/` are
discovered automatically. Ask it to "bring up the Lithrim stack" or "run my first grade" and it uses
them. Nothing to install.

### If you did not clone (fetch the skills only)

Install the three skills into your personal skills directory so they are available in any project.
No clone, no build:

```bash
for s in lithrim-docker-up lithrim-first-grade lithrim-snomed-setup; do
  mkdir -p ~/.claude/skills/"$s"
  curl -fsSL "https://raw.githubusercontent.com/lithrim-dev/lithrim/main/.claude/skills/$s/SKILL.md" \
    -o ~/.claude/skills/"$s"/SKILL.md
done
```

Restart Claude Code (or start a new session) so it picks up the new skills. To scope them to one
project instead of your whole account, use that project's `.claude/skills/` in place of
`~/.claude/skills/`.

To update later, re-run the same command. To remove a skill, delete its directory.

---

## A note on clone vs. no-clone

The skills are written to work on both paths, but two steps genuinely need the source, because they
run the Python engine directly rather than the containers:

- **`lithrim-first-grade` stage 1 (the `$0` offline demo)** runs `make demo`, which needs the repo
  checked out and `pip install -e .`. On the no-clone path, skip stage 1 and start from the running
  stack; you lose the offline warm-up, not the grade.
- A few steps reference shipped files by their in-repo path (for example
  `samples/quickstart/notes.jsonl`). Without a clone, fetch those by URL (see
  [`docs/DEPLOY.md`](DEPLOY.md) section 3) or use your own JSON / JSONL / CSV.

Everything that drives the running stack (`lithrim-docker-up` in full, `lithrim-first-grade` stages 2
onward, all of `lithrim-snomed-setup`) works identically whether or not you cloned.

---

## Safety boundaries these skills respect

These are baked into the skill instructions, not optional:

- **No autostart of privileged commands.** If a step needs elevation, the skill stops and tells you
  what to run.
- **You authorize spend.** The one paid step (a live grade) opens a cost-confirm dialog that **you**
  click. The skill never confirms a paid run for you.
- **Your key is never echoed.** Keys are entered by you in the UI or a local `.env`; the skill does
  not print them to chat or logs.
- **SNOMED licensing is a hard gate.** `lithrim-snomed-setup` will not download or automate acquiring
  any SNOMED CT release. You obtain a licensed release yourself and give it the on-disk path. The
  Hermes software is open source and fine to fetch; the terminology data is not.

---

## Related docs

- [`docs/DEPLOY.md`](DEPLOY.md): run the prebuilt stack (what `lithrim-docker-up` automates).
- [`SETUP.md`](../SETUP.md): the manual first-grade walkthrough (what `lithrim-first-grade` automates).
- [`docs/SNOMED_SETUP.md`](SNOMED_SETUP.md): the full SNOMED guide (what `lithrim-snomed-setup` automates).
