# ADR 002 — Validate the Dojo Scaffold in a Container via Jenkins

| Status | Date       | Project Version |
|--------|------------|-----------------|
| Draft  | 2026-08-06 | 0.0.1           |

## Context

`make r` (repo root) syncs the automated-test scaffold's uv environment and runs its non-hardware
suite — the smoke check that the scaffold itself is healthy (ADR 001, `docs/ARCHITECTURE.md`). Until
now it only ever ran on a developer's machine, which weakens exactly the claim dojo makes: that a
new project can copy `source/tests/automated/`, follow `readme.md`, and get a working environment.

A developer box is the worst place to prove that claim. It already has `uv` on `PATH`, a warm
`.venv` from a previous sync, a system Python that happens to satisfy `.python-version`, and
whatever else accumulated there. All of those can mask a scaffold that would fail on a clean
machine — a dependency that resolves only from a stale cache, a `readme.md` setup step that no
longer works, a lockfile that no longer matches `pyproject.toml`.

`source/Jenkinsfile` does not solve this. It is a *template* for consuming projects: it carries
`<AGENT_LABEL>`/`<REPO_URL>`/`<SSH_PASSWORD_CREDENTIAL_ID>` placeholders, requires a flashed target
at `TARGET_HOST`, and runs the `hardware`-marked tests. Dojo has no target device, so that pipeline
cannot run against dojo itself and never will. Dojo ships CI for others while having none of its
own.

The sibling projects on the same Jenkins controller (`riker`, `kobayashi_maru`, `SleepyDog`) have
already converged on a shape for this: a `docker/` directory holding the build environment, a
`Jenkinsfile.docker` at the repo root, and a Docker-first policy where the pipeline shells into a
container rather than depending on tools installed on the agent.

## Decision drivers

- A green build must mean "the documented setup works on a machine that has never seen this repo",
  not "it works on the machine that already had it working".
- CI must run the *same* command a developer runs (`make r`), not a CI-only variant that can drift
  away from what the Makefile and `readme.md` describe.
- Dojo's own pipeline should read like the other jobs on the controller — a maintainer moving
  between repos should not have to learn a second pipeline idiom.
- Nothing about dojo's validation needs hardware, so it must not borrow the HIL template's
  agent-label or credential requirements.

## Decision

Add a container-based validation pipeline for dojo itself, kept clearly distinct from the HIL
template it ships:

- **`docker/Dockerfile`** — digest-pinned `ubuntu:24.04` (foundry ADR 017 convention) plus
  `make`, `git`, `curl`, `ca-certificates`, and nothing else. `uv` is installed with the *unpinned*
  installer command copied verbatim from `source/tests/automated/readme.md`, so the build exercises
  the documented setup step rather than a pinned variant that could keep passing while the docs rot.
- **`docker/docker-compose.yml`** — one `dojo-dev` service, repo bind-mounted at `/workspace`.
  Local use and CI use are the same two commands; there is no CI-only invocation path.
- **`Jenkinsfile.docker`** (repo root) — Checkout, Setup Docker Environment, Scaffold Validation
  (`make r` in the container), then `junit` + `archiveArtifacts` on `source/tests/output/`. Stage
  layout, `agent any`, per-stage timeouts, and SSH-deploy-key checkout follow
  `riker/Jenkinsfile.docker`.
- **Jenkins job `Dojo-Docker`** — a pipeline job on the VEDA controller reading `Jenkinsfile.docker`
  from `git@github.com:mhouse1/dojo.git` via the `github-mhouse1-ssh` credential, with
  `TARGET_BRANCH` and `CLEAN_BUILD` parameters, matching the `Riker-Docker` job's configuration.

Two details are load-bearing enough to state explicitly:

- **The container runs as uid/gid 1000**, the same uid the Jenkins controller runs as. A root
  container writing into the bind-mounted workspace leaves root-owned test output that the next
  build's checkout cannot delete — a failure mode SleepyDog's pipeline works around after the fact
  with a root `rm -rf`. Matching the uid avoids creating the problem.
- **The venv lives at `/opt/dojo/venv`, outside the bind mount** (`UV_PROJECT_ENVIRONMENT`,
  `VIRTUAL_ENV`). A `.venv` inside `/workspace` would clobber, or be clobbered by, the developer's
  host venv when run locally, and would leave a large directory behind in the Jenkins workspace
  after every build. The scaffold Makefile's `uv run --active` resolves to this environment
  unchanged, so the Makefile needs no CI-specific branch.

The image pre-fetches the pinned interpreter and pre-builds the venv from the committed lockfile at
image-build time. `make r` still runs `uv sync --all-groups` itself against the checked-out
lockfile at run time — that sync is the actual check — but it resolves to a fast no-op when nothing
moved. `CLEAN_BUILD` forces a `--no-cache` rebuild for the genuine from-scratch case.

## Consequences

**Positive**

- The claim dojo makes about its scaffold is now tested rather than asserted: a from-scratch
  environment build plus the documented `uv sync` plus the suite, on every run.
- Dojo has CI of its own, on the same controller and in the same idiom as its sibling projects.
- Regressions in the parts of the scaffold that have no test — `readme.md`'s setup steps, the
  lockfile/`pyproject.toml` agreement, the `.python-version` pin — surface as build failures.

**Negative / risks**

- The unpinned `uv` installer means an upstream `uv` release can turn a build red without any
  change to this repo. That is deliberate — it is the signal the pipeline exists to produce — but
  it does mean a red build is not always dojo's fault, and the fix may belong in `readme.md`.
- The base-image digest is a manual bump. It will drift from `ubuntu:24.04` until someone updates
  it, which is the accepted cost of the foundry ADR 017 pinning convention.
- Two Jenkins files now live in the repo. `source/Jenkinsfile` (HIL template, for consumers) and
  `Jenkinsfile.docker` (dojo's own CI) are easy to confuse; both carry header comments saying which
  is which.
- Hardware-marked tests still never run anywhere. This pipeline validates the scaffold's
  environment and its hardware-independent tests only — it does not, and cannot, prove the SSH and
  serial code paths work against a real target.

## Alternatives considered

1. **Run `make r` directly on the Jenkins agent, no container.** Rejected — reintroduces exactly the
   contamination the change is meant to eliminate (agent-installed `uv`, a persisted workspace
   `.venv`), and makes dojo the only job on the controller that is not Docker-first.
2. **Fill in `source/Jenkinsfile`'s placeholders and point it at dojo.** Rejected — that file is a
   deliverable for consumers to copy, not dojo's own pipeline. Filling it in would either bake
   dojo's repo URL and credential IDs into the template consumers copy, or require maintaining a
   filled-in fork of it.
3. **Use a GitHub Actions workflow instead.** Rejected — the toolchain, credentials, and every
   sibling project already live on the VEDA Jenkins controller; a second CI system for one repo
   splits where results are found for no gain.
4. **Add a `make docker` target wrapping the compose commands.** Deferred, not rejected. The two
   compose commands are documented in `docker/docker-compose.yml`'s header and in
   `docs/ARCHITECTURE.md`; a wrapper target can follow if it turns out to be typed often enough to
   earn a place beside the existing single-letter targets.
