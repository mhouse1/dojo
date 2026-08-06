# Dojo scaffold-validation environment.
#
# Runs `make r` (uv sync + the non-hardware pytest suite) in a container that
# starts from nothing but Ubuntu - so a green build proves the automated-test
# scaffold installs and passes on a machine that has never seen this repo, not
# just on a developer box with a warm .venv. See
# docs/adr/002-containerize-scaffold-validation.md.
#
# Digest-pinned (foundry ADR 017, same convention as riker/docker/Dockerfile):
# unpinned tags make rebuilds produce entirely new layer sets whenever upstream
# updates. To bump: docker pull ubuntu:24.04 && docker buildx imagetools inspect ubuntu:24.04
FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# curl + ca-certificates: fetch uv. git: the scaffold is checked out by Jenkins,
# but pytest/uv both behave better with git present. make: the command surface
# local dev and CI share (HLDD 001).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    make \
    && rm -rf /var/lib/apt/lists/*

# Run as uid/gid 1000 - the same uid the Jenkins controller runs as (jenkins:1000),
# so files this container writes into the bind-mounted workspace (test output,
# .pytest_cache) stay deletable by the next build's checkout instead of landing
# root-owned. ubuntu:24.04 already ships a placeholder user at 1000; replace it.
RUN userdel -r ubuntu 2>/dev/null || true && \
    groupadd -g 1000 dojo && \
    useradd -m -u 1000 -g 1000 -s /bin/bash dojo

# The venv lives outside /workspace on purpose: /workspace is a bind mount of the
# repo, so a .venv created there would either be clobbered by (or clobber) the
# developer's host venv, and would leave a multi-hundred-MB directory behind in
# the Jenkins workspace after every build. VIRTUAL_ENV makes the scaffold
# Makefile's `uv run --active` resolve to this same environment.
#
# It sits one level down, in a /opt/dojo the dojo user owns, rather than directly
# in /opt: switching interpreters at run time (UV_PYTHON=3.12 make sync) makes uv
# delete and recreate the venv directory, and removing a directory needs write
# permission on its *parent*, not on the directory itself. With the venv directly
# in root-owned /opt, that swap fails with "failed to remove directory ...:
# Permission denied" - and only on the run-time-override path, since a CI matrix
# cell gets an image already built at its own version.
ENV UV_PROJECT_ENVIRONMENT=/opt/dojo/venv
ENV VIRTUAL_ENV=/opt/dojo/venv
RUN mkdir -p /opt/dojo/venv && chown -R 1000:1000 /opt/dojo

USER dojo
# Both entries matter: uv installs itself into ~/.local/bin, and putting the
# venv's bin first is what "activated" actually means to anything that isn't uv
# (a bare `python`/`pytest`, the Makefile's non-uv fallback path). VIRTUAL_ENV
# above and this PATH entry are the two halves of the same activation.
ENV PATH="/opt/dojo/venv/bin:/home/dojo/.local/bin:${PATH}"

# Deliberately the unpinned installer from source/tests/automated/readme.md's
# "Setup" section: this pipeline's job is to prove that the documented setup
# steps still work for a new consumer of the scaffold, so it runs the documented
# command rather than a pinned variant that could pass while the docs rot.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Which interpreter this image validates against. Deliberately given no default:
# left unset, everything below falls back to the .python-version copied in, so a
# plain `docker compose build` always matches what `make r` gives a developer on
# the host - there is no second copy of the version here, free to drift from the
# real one. The CI matrix sets it per cell (Jenkinsfile.docker's PYTHON_VERSIONS).
#
# It has to be UV_PYTHON specifically, not just a build-time flag: `make r` runs
# its own `uv sync` at container run time, and UV_PYTHON is what outranks
# .python-version there. Without it a 3.12 cell would re-sync itself to whatever
# .python-version pins and silently report a pass for the wrong interpreter.
#
# Declared after the apt and uv-installer layers on purpose: changing it should
# only invalidate the interpreter and venv layers below, not rebuild the world.
ARG PYTHON_VERSION
ENV UV_PYTHON=${PYTHON_VERSION}

# Pre-fetch the interpreter .python-version pins and pre-build the venv from the
# lockfile, so a build only pays for what actually changed. `make r` still runs
# `uv sync --all-groups` itself at run time - against the checked-out lockfile,
# which is the real check - but that resolves to a fast no-op when nothing moved.
COPY --chown=dojo:dojo source/tests/automated/.python-version \
                       source/tests/automated/pyproject.toml \
                       source/tests/automated/uv.lock \
                       source/tests/automated/readme.md \
                       /opt/dojo-prewarm/
WORKDIR /opt/dojo-prewarm
# Resolve the version explicitly rather than leaning on uv's own fallbacks: with
# UV_PYTHON set but empty (what an unset PYTHON_VERSION build arg produces),
# `uv sync` falls back to .python-version happily but `uv python install` fails
# with "`` is not a valid Python download request". Pinning PY here means both
# commands get the same non-empty answer, whichever way the build was invoked.
RUN PY="${UV_PYTHON:-$(cat .python-version)}" && \
    echo "building against Python ${PY}" && \
    UV_PYTHON="${PY}" uv python install "${PY}" && \
    UV_PYTHON="${PY}" uv sync --all-groups

# Fail the build, not a test run, if the image ended up on a different
# interpreter than was asked for - the failure this guards against is silent:
# the suite passes, and the report says 3.14 while 3.10 actually ran it.
# Compared on major.minor so a .python-version pinned to a patch release
# ("3.14.7") checks out the same as one pinned to a series ("3.14").
RUN PY="${UV_PYTHON:-$(cat .python-version)}" && \
    want="$(echo "${PY}" | cut -d. -f1,2)" && \
    got="$(/opt/dojo/venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" && \
    if [ "${want}" != "${got}" ]; then \
        echo "ERROR: asked for Python ${want}, image has ${got}"; exit 1; \
    fi && \
    echo "image verified on Python ${got}"

WORKDIR /workspace
