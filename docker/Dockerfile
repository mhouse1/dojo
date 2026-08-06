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
ENV UV_PROJECT_ENVIRONMENT=/opt/dojo-venv
ENV VIRTUAL_ENV=/opt/dojo-venv
RUN mkdir -p /opt/dojo-venv && chown 1000:1000 /opt/dojo-venv

USER dojo
# Both entries matter: uv installs itself into ~/.local/bin, and putting the
# venv's bin first is what "activated" actually means to anything that isn't uv
# (a bare `python`/`pytest`, the Makefile's non-uv fallback path). VIRTUAL_ENV
# above and this PATH entry are the two halves of the same activation.
ENV PATH="/opt/dojo-venv/bin:/home/dojo/.local/bin:${PATH}"

# Deliberately the unpinned installer from source/tests/automated/readme.md's
# "Setup" section: this pipeline's job is to prove that the documented setup
# steps still work for a new consumer of the scaffold, so it runs the documented
# command rather than a pinned variant that could pass while the docs rot.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

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
RUN uv python install && uv sync --all-groups

WORKDIR /workspace
