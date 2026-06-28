# Security Policy

Lithrim is a self-hosted developer tool. It runs on your machine, against
your own model keys (BYOK), and sends nothing to a Lithrim-hosted service — most
of the security surface is yours to control. We still take vulnerabilities in the
harness itself seriously.

## Supported versions

Lithrim is pre-1.0. Security fixes land on `main` and in the most recent
tagged release. There is no long-term-support branch yet.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting for this repository:
**Security → Report a vulnerability**.
<!-- maintainer: optionally add a dedicated security contact email here. -->

Please include:

- a description of the issue and the impact you observed,
- the steps or a minimal case to reproduce it,
- the version / commit you tested,
- any suggested remediation.

We aim to acknowledge within a few business days and to agree a disclosure
timeline with you. Reporters who want credit will get it.

## Out of scope

- Findings produced **by** the harness (judge votes, floor verdicts) — that's
  evaluation output, not a vulnerability. Use a normal issue.
- Issues that require already having write access to the machine running the tool.
- The security posture of model providers you connect via BYOK.

## Handling secrets

Provider keys are read from environment files (`.env`, `.live_env`,
`.connector_env`, `.provider_env`) that are **gitignored by design** — never
commit them. The only env file in version control is
[`.env.example`](.env.example), which holds placeholders only. If you believe a
secret was committed, treat it as compromised: rotate the key and report it.
