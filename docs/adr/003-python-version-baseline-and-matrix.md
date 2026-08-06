# ADR 003 — Python Version Baseline and Opt-In CI Matrix

| Status | Date       | Project Version |
|--------|------------|-----------------|
| Draft  | 2026-08-06 | 0.0.1           |

## Context

The scaffold pinned Python 3.10 in `source/tests/automated/.python-version`, inherited from
mos-docker via ADR 001 rather than chosen. Two things make that worth revisiting: 3.10 reaches end
of life in October 2026, and dojo exists to be copied — a scaffold that starts a new project on an
interpreter about to go unsupported starts it with debt.

The containerised validation from ADR 002 made the question answerable by measurement instead of
argument. Running the non-hardware suite against each interpreter in turn:

| Interpreter | Dependencies | Result |
|---|---|---|
| 3.11.15, 3.12.13, 3.13.14 | committed pins | 47 passed |
| 3.14.7 (latest stable) | committed pins, and `uv sync` from the committed lock | 47 passed |
| 3.15.0rc1 | committed pins | 47 passed |
| 3.14.7 | newest available: paramiko 5.0.0, pytest 9.1.1, cryptography 50.0.0, scp 0.16.1 | 47 passed |

Nothing needed changing to get those results — no code edits, no re-locking, and no source builds
(every dependency resolved to a wheel, which matters because the image ships no compiler). The
scaffold turned out to be portable already; it was pinned low, not written low.

One caveat bounds all of it: **only the non-hardware suite ran.** Everything in `coms.py`'s SSH and
serial paths, and `power_control.py`'s transports against a real device, has never run in CI on any
interpreter. paramiko 5.0.0 is a major version bump, and these results say nothing about whether
SSH still works against a real target.

A first attempt at this measurement produced the right answer for the wrong reason and is worth
recording as the hazard it is: `uv run --active` re-syncs the project environment, so a run
launched as 3.14 silently recreated its venv at whatever `.python-version` pinned and reported a
pass for an interpreter it never executed. Every number above comes from pytest's own
`platform ... -- Python X.Y.Z` header instead of from what was requested.

## Decision drivers

- A scaffold's default should be the interpreter a new project would sensibly start on today.
- What dojo develops against and what the scaffold *supports* are different questions and should
  not be conflated into one pin.
- Per-commit CI cost should not multiply just because a range is supported.
- A version matrix is worthless if a cell can silently run the wrong interpreter — the failure mode
  is a green build attesting to a version that never ran.

## Decision

**Move the baseline to 3.14, keep the supported floor at 3.10.** `.python-version` becomes `3.14`;
`requires-python` stays `>=3.10` so a project on an older interpreter can still adopt the scaffold.
`uv.lock` is unchanged — verified to install and pass on 3.14 as committed. The floor should rise
when 3.10 goes end of life in October 2026.

**Make the matrix opt-in, not always-on.** `Jenkinsfile.docker` gains a `PYTHON_VERSIONS` string
parameter. Empty (the default) runs exactly one cell against whatever `.python-version` pins, so
the per-commit cost is unchanged; `"3.10,3.12,3.14"` fans out one parallel cell per interpreter.
Declarative Jenkins `matrix` axes cannot be driven by a build parameter, so the fan-out is built
with `parallel` from the parsed parameter instead.

**Drive the interpreter through `UV_PYTHON`, not the build alone.** `make r` runs its own `uv sync`
at container run time, and `UV_PYTHON` is what outranks `.python-version` there. A build-time flag
alone would let a 3.12 cell re-sync itself to the pinned version mid-run — the exact hazard
described above, now on the CI's side.

Four supporting details, each guarding a failure that is silent rather than loud:

- **No default for the `PYTHON_VERSION` build arg**, in either the Dockerfile or the compose file.
  Unset, everything falls back to the copied `.python-version`, so there is no second copy of the
  pinned version free to drift from the real one. The default image tag is `dojo-dev:pinned` for
  the same reason.
- **The image asserts its own interpreter at build time**, and each CI cell re-checks pytest's
  `platform` header after the run. A cell that ends up on the wrong interpreter fails instead of
  reporting a pass for a version it never ran.
- **Each cell gets its own `OUTPUT_DIR`** (`make r OUTPUT_DIR=...`, a make command-line variable, so
  it overrides the Makefile and propagates to its sub-makes). Parallel cells share one Jenkins
  workspace and would otherwise overwrite each other's `junit.xml`.
- **Each cell sets `junit_suite_name`** so Jenkins can tell identically-named tests apart after it
  merges every cell's XML, and `-p no:cacheprovider` so cells do not race on one `.pytest_cache`.

**Remove the scaffold's only private-API use.** The `step` fixture wrote to `request.node._store`,
pytest's private stash, and nothing read the value back. Deleted rather than ported to the public
`node.stash`, since the stored value was dead.

## Consequences

**Positive**

- New projects copying the scaffold start on the current interpreter rather than one months from
  end of life.
- The supported range is now testable on demand rather than assumed, and each result is attested by
  the interpreter that actually ran.
- Checking a new interpreter costs one parameter, not a branch: `PYTHON_VERSIONS=3.15` answers
  "does the next release break us" before it ships.
- The scaffold no longer depends on any private pytest API.

**Negative / risks**

- Nothing runs the matrix automatically, so the supported floor can rot between deliberate runs. A
  scheduled trigger would fix it and is deliberately not added here — see alternative 4.
- Matrix cells share one workspace. Per-cell `OUTPUT_DIR` and a disabled pytest cache cover the
  collisions that exist today; a future stage writing to a fixed path would reintroduce the problem.
- 3.14 is newer than some agents' system Python. This costs nothing here because uv downloads its
  own interpreter, but a consuming project that ignores uv and uses the system Python will notice.
- The measurements behind this decision cover the non-hardware suite only (see Context).

## Alternatives considered

1. **Stay on 3.10.** Rejected — end of life is two months out, and the measurement shows nothing
   was holding the scaffold there.
2. **Move to 3.15.** Rejected — 3.15.0rc1 passes, but shipping a scaffold's default on a release
   candidate makes every consuming project an early adopter without being asked. Worth revisiting
   once 3.15 is stable.
3. **tox or nox for the matrix.** Rejected — adds a second command surface beside the Makefile,
   which HLDD 001 calls the one surface CI and local dev share, to do something uv already does
   natively.
4. **Run the matrix on every commit.** Rejected as the default — it multiplies per-commit CI time
   by the number of interpreters to re-prove something that changes only when dependencies or
   interpreters do. A periodic scheduled run is the better shape and can be added by pointing a
   cron trigger at this job with `PYTHON_VERSIONS` set, without touching the pipeline.
5. **Raise `requires-python` to `>=3.14` to match the pin.** Rejected — it would lock out consumers
   on supported older interpreters for no benefit, and conflates dojo's development baseline with
   the scaffold's supported range.
