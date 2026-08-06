# Dojo

A copyable starting point for new projects: a system-agnostic ROE (Rules of Engagement)
documentation scaffold, plus working source-code scaffolds you can drop into a new repo instead of
starting from a blank file.

Dojo has two halves:

- **`docs/`** — the ROE scaffold: `AGENTS.md`'s rules (numbering, heading format, ADR/HLDD/roadmap
  conventions) and the numbered subdirectories (`docs/adr/`, `docs/hldd/`, `docs/roadmap/`,
  `docs/job-aid/`, `docs/performance/`, `docs/code-review/`) they govern.
- **`source/`** — working code scaffolds. Currently: an automated hardware-in-the-loop (HIL) pytest
  test suite (`source/tests/automated/`) plus a template CI pipeline (`source/Jenkinsfile`) — see
  `docs/hldd/001-automated-test-scaffold.md` for what it is and
  `docs/adr/001-adopt-mos-docker-hil-test-suite-architecture.md` for why it's shaped the way it is.

## Quickstart

To use dojo as a starting point for a new project:

1. Copy `AGENTS.md`, `CONTRIBUTING.md`, and the `docs/` tree into the new project, adapting
   `AGENTS.md`'s rules if the new project needs additions beyond the base ROE.
2. Copy `source/tests/automated/` and `source/Jenkinsfile` if the new project needs embedded HIL
   testing — see that directory's own `readme.md` for the fill-in-the-placeholders steps.

To validate dojo's own scaffold (uv installs cleanly, baseline tests pass):

```
make r
```

To run that same check from a clean machine instead of your own — the container starts from a bare
Ubuntu image, so it also proves `source/tests/automated/readme.md`'s setup steps still work:

```
docker compose -f docker/docker-compose.yml build dojo-dev
docker compose -f docker/docker-compose.yml run --rm dojo-dev make r
```

`Jenkinsfile.docker` runs exactly those two commands in CI (the `Dojo-Docker` Jenkins job). It is
dojo's own pipeline — not `source/Jenkinsfile`, which is the HIL template consuming projects copy.
See `docs/adr/002-containerize-scaffold-validation.md`.

## docs/

All documentation lives under `docs/`. See `AGENTS.md` for numbering and heading format rules, and
`docs/ARCHITECTURE.md` for the current-state overview of this repo.
